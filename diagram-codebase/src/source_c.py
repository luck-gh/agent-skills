"""提取未预处理的 C 源码结构,不定位 SDK,不读取 include 目标或求解符号.

由 offline_scan 的 source 模式调用,也供环境探测用内存样例验证.
使用 Tree-sitter 的 C 语法树保留条件分支,调用表达式只作待核对线索.
"""


import re


def decode_source(raw):
    """严格解码 C 源码,返回文本与编码;不替换非法字节或修改原文件."""
    try:
        return raw.decode('utf-8-sig'), 'utf-8'
    except UnicodeDecodeError:
        return raw.decode('gb18030'), 'gb18030'


def syntax_view(source):
    """保留位置的不透明语法视图,仅识别实际遇到的 CMSIS/ARM 注解和 C++ linkage 包装."""
    spans = []
    # 先跳过注释和字符串,不能把其中的注解字面量当作代码.
    tokens = re.compile(rb'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"|'
                        rb"'(?:\\[\s\S]|[^'\\])*'|\b__(?:I|O|IO)\b|"
                        rb'\b__align[ \t]*\([ \t]*[0-9]+[ \t]*\)')
    for match in tokens.finditer(source):
        token = match.group()
        prefix = source[source.rfind(b'\n', 0, match.start()) + 1:match.start()]
        if token.startswith(b'__') and not prefix.strip():
            spans.append((match.start(), match.end(), 'compiler-annotation-opaque'))
    opening = re.compile(rb'(?m)^[ \t]*#[ \t]*ifdef[ \t]+__cplusplus[ \t]*\r?\n'
                         rb'(?P<code>[ \t]*extern[ \t]+"C"[ \t]*\{[ \t]*)\r?\n'
                         rb'[ \t]*#[ \t]*endif[^\n]*(?:\n|$)')
    closing = re.compile(rb'(?m)^[ \t]*#[ \t]*ifdef[ \t]+__cplusplus[ \t]*\r?\n'
                         rb'(?P<code>[ \t]*\}[ \t]*)\r?\n'
                         rb'[ \t]*#[ \t]*endif[^\n]*(?:\n|$)')
    opens, closes = list(opening.finditer(source)), list(closing.finditer(source))
    if len(opens) == len(closes) and all(a.end() <= b.start() for a, b in zip(opens, closes)):
        for match in (*opens, *closes):
            start, end = match.span('code')
            # 仅处理词法扫描确认不在注释或字符串中的包装代码.
            if any(t.start() < start < t.end() for t in tokens.finditer(source)):
                continue
            spans.append((start, end, 'cpp-linkage-wrapper-opaque'))
    view = bytearray(source)
    annotations = []
    for start, end, kind in sorted(spans):
        view[start:end] = b' ' * (end - start)
        annotations.append({'kind': kind, 'line': source.count(b'\n', 0, start) + 1,
                            'spelling': source[start:end].decode('utf-8').strip()})
    return bytes(view), annotations


def parse(source, relative):
    from tree_sitter import Language, Parser
    import tree_sitter_c

    content, encoding = decode_source(source)
    source = content.encode('utf-8')
    view, annotations = syntax_view(source)
    tree = Parser(Language(tree_sitter_c.language())).parse(view)
    result = {'status': 'partial' if tree.root_node.has_error else 'ok',
              'symbols': [], 'edges': [], 'dependencies': {}, 'diagnostics': [
                  'C source syntax only: no includes loaded, macros expanded, build selection or target resolution. '
                  'Conditions are unevaluated; call expressions may name functions, pointers or macros.']}

    result['source_encoding'] = encoding
    result['syntax_annotations'] = annotations
    if encoding != 'utf-8':
        result['diagnostics'].append(f'Source decoded strictly as {encoding}; original bytes unchanged.')
    if annotations:
        result['diagnostics'].extend(f"Opaque {a['kind']}: {a['spelling']} at line {a['line']}; no macro expansion or ABI claim." for a in annotations)

    def text(node, limit=500):
        return source[node.start_byte:node.end_byte].decode('utf-8')[:limit] if node else ''

    def line(node):
        # py-tree-sitter 0.26 的 Point.row getter 返回借用引用;元组索引返回拥有引用.
        return node.start_point[0] + 1

    def symbol(node, name, kind, signature, conditions, parameters=None):
        value = {'id': f'{relative}:{line(node)}:{name}:{node.start_byte}:{kind}', 'name': name, 'kind': kind,
                 'line': line(node), 'end': node.end_point[0] + 1,
                 'signature': signature, 'conditions': list(conditions)}
        if parameters is not None:
            value['parameters'] = parameters
        result['symbols'].append(value)
        return value['id']

    def edge(node, owner, kind, target, conditions, **fields):
        result['edges'].append({'owner': owner, 'kind': kind, 'target': target,
                               'line': line(node), 'conditions': list(conditions), **fields})

    def declaration_name(node):
        while node is not None:
            if node.type in {'identifier', 'type_identifier', 'field_identifier'}:
                return text(node)
            if node.type == 'parenthesized_declarator' and len(node.named_children) == 1:
                node = node.named_children[0]
                continue
            node = node.child_by_field_name('declarator')
        return ''

    def walk(node, owner=None, conditions=()):
        kind = node.type
        if node.is_error or node.is_missing:
            result['diagnostics'].append(f'Syntax {"missing" if node.is_missing else "error"} at line {line(node)}; partial evidence only.')
        if kind in {'preproc_if', 'preproc_ifdef', 'preproc_elif', 'preproc_elifdef'}:
            condition = node.child_by_field_name('condition') or node.child_by_field_name('name')
            directive = next((text(c) for c in node.children if c.type.startswith('#')), '#if')
            label = f'{directive} {text(condition, 300)} @line {line(node)}'
            edge(node, owner, 'preprocessor-condition-not-evaluated', label, conditions)
            alternative = node.child_by_field_name('alternative')
            for child in node.children:
                if child != condition and child != alternative:
                    walk(child, owner, (*conditions, label))
            if alternative is not None:
                walk(alternative, owner, (*conditions, f'NOT ({label})'))
            return
        if kind in {'preproc_def', 'preproc_function_def'}:
            name = text(node.child_by_field_name('name'))
            symbol(node, name, 'macro-definition-not-expanded', text(node), conditions)
            return  # Macro bodies are opaque; do not invent expanded calls or returns.
        if kind == 'preproc_include':
            edge(node, owner, 'include-reference-not-loaded', text(node.child_by_field_name('path')), conditions)
            return
        if kind == 'function_definition':
            declarator = node.child_by_field_name('declarator')
            body = node.child_by_field_name('body')
            name = declaration_name(declarator)
            if not name or body is None:
                result['status'] = 'partial'
                result['diagnostics'].append(f'Unresolved function declarator at line {line(node)}')
            else:
                signature = source[node.start_byte:body.start_byte].decode('utf-8').strip()[:500]
                owner = symbol(node, name, 'function', signature, conditions)
        elif kind in {'declaration', 'type_definition'} and owner is None:
            for child in node.children_by_field_name('declarator'):
                name = declaration_name(child)
                if name:
                    symbol(node, name, 'source-declaration', text(node), conditions)
        elif kind in {'struct_specifier', 'union_specifier', 'enum_specifier'} and owner is None:
            name = text(node.child_by_field_name('name'))
            if name:
                symbol(node, name, kind, f'{kind} {name}', conditions)
        elif kind == 'call_expression':
            target = node.child_by_field_name('function')
            edge(node, owner, 'call-expression-unresolved' if target and target.type == 'identifier'
                 else 'indirect-call-expression', text(target, 300), conditions,
                 arguments=text(node.child_by_field_name('arguments'), 300))
        elif kind == 'pointer_expression' and text(node.child_by_field_name('operator')) == '&':
            edge(node, owner, 'address-expression-not-call', text(node.child_by_field_name('argument'), 300), conditions)
        elif kind in {'if_statement', 'switch_statement', 'return_statement', 'break_statement',
                      'continue_statement', 'for_statement', 'while_statement', 'do_statement', 'goto_statement'}:
            value = node.child_by_field_name('condition')
            # Control statements with bodies must not copy the whole body into the index.
            target = text(value, 300) if value else (text(node, 300) if kind in {
                'return_statement', 'break_statement', 'continue_statement', 'goto_statement'} else '')
            edge(node, owner, kind, target, conditions)
        for child in node.children:
            walk(child, owner, conditions)

    walk(tree.root_node)
    return result
