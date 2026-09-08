# 按需初始化离线解析环境

本分支只准备开源解析依赖,不是创建/重装 Skill.目标工程扫描由 [offline-analysis.md](offline-analysis.md) 的统一入口执行;环境探测不能代替工程扫描.不调用兄弟 Skill 的运行时代码,不运行 initializer,不接入全局发现入口.

## 选择与边界

优先复用用户明确指定的解释器,先运行对应 profile 的探测.不为一次 Markdown 或 Python 分析安装 C/HDL 工具.混合工程只组合所需 profile.不把包已安装等同于动态库能加载,也不把内置样例成功等同于目标工程能解析.

| profile | 固定工具 | 来源与许可证 | 下载量及边界 |
| --- | --- | --- | --- |
| python | Python 标准库 ast | Python 自带,PSF License | 无额外包.只解析,不 import/运行用户工程. |
| markdown | markdown-it-py 4.0.0,mdurl 0.1.2 | [markdown-it-py](https://github.com/executablebooks/markdown-it-py),[mdurl](https://github.com/executablebooks/mdurl),均 MIT | 两个 wheel 合计 97,300 bytes,随包离线安装.标准 Markdown;不自动理解 Skill 条件或 Obsidian 双链语义. |
| c-source | tree-sitter 0.26.0,tree-sitter-c 0.24.2 | [Python binding](https://github.com/tree-sitter/py-tree-sitter),[C grammar](https://github.com/tree-sitter/tree-sitter-c),均 MIT | Windows wheel 分别为 129,619 和 84,669 bytes,合计 214,288 bytes.源码结构模式,不需要 MCU SDK/编译器;不展开宏,不解析调用目标或当前构建变体. |
| c | libclang 18.1.1 | [社区 libclang 打包项目](https://github.com/sighingnow/libclang),Apache-2.0 WITH LLVM-exception | Windows wheel 约 26.4 MB,自带动态库.不是 LLVM 官方 PyPI 发行,不装同名空间但不带库的 clang 包.不提供 MCU SDK/项目头文件或完整 LLVM 工具链. |
| hdl | pyslang 11.0.0 | [slang 官方项目](https://github.com/MikePopoloski/slang),MIT | Windows CPython 3.12 wheel 约 3.5 MB,自带 slang.用于数字 Verilog/SystemVerilog,不支持 Verilog-A. |

每个 artifact 的 SHA-256 和精确版本保存于 [C 锁文件](../tools/bundled/c-win-cp312.txt),[HDL 锁文件](../tools/bundled/hdl-win-cp312.txt),[Markdown 锁文件](../tools/bundled/markdown-win-cp312.txt).镜像只改变下载位置,不改变锁文件或包版本.Markdown 不为追最新版本而替换已验收版本.锁文件使用已验收 artifact 的 hash,不是所有操作系统通用的安装清单.

C 源码分支使用独立的 [c-source 锁文件](../tools/bundled/c-source-win-cp312.txt).源码模式仅需 c-source,配置模式仅需 c,不是每次都装两套.C 源码包虽小但含平台原生库,本版只将锁文件纳入 Git,原始 wheel 下载在 tools/local/win-cp312/downloads/,不新增 bundled 二进制.来源为对应官方项目的 PyPI 发行,原包中的 MIT 许可证和作者声明保持完整.树解析依赖不是目标工程环境,无需安装 Tree-sitter CLI 或生成语法库.

## Git 与分发

所有离线依赖统一归入 tools/:bundled/ 保存纳入 Git 的锁文件和获准随包的原始小包;local/ 保存不纳入 Git 的本机下载与安装环境.不要忽略整个 tools/,也不要在 bundled/ 中安装 venv.空的 local/ 不随 Git 分发,初始化时按需创建.

- 自有脚本,模板,锁文件和本文进入源码管理.已获准随 Skill 保存的第三方包仅为 tools/bundled/wheels/ 下的两个原始 Markdown wheel,体积小且为纯 Python;不解包改写,不删减许可证.获得 Skill 文件后,Markdown 依赖安装不需访问任何包站点,但机器仍需有兼容 Python.
- [markdown_it_py-4.0.0-py3-none-any.whl](../tools/bundled/wheels/markdown_it_py-4.0.0-py3-none-any.whl) 原包包含 markdown_it_py-4.0.0.dist-info/licenses/LICENSE 和 LICENSE.markdown-it;[mdurl-0.1.2-py3-none-any.whl](../tools/bundled/wheels/mdurl-0.1.2-py3-none-any.whl) 包含 mdurl-0.1.2.dist-info/LICENSE.其中原始作者与移植代码声明一并保留.来源为上述项目的 PyPI 发行,哈希以锁文件为准.
- libclang-18.1.1-py2.py3-none-win_amd64.whl 为 26,415,083 bytes,pyslang-11.0.0-cp312-cp312-win_amd64.whl 为 3,522,100 bytes.二者含平台原生库,后续平台/版本会增加二进制副本,因此不随 Git 保存,使用下面的固定下载安装或外置离线包.
- 下载包和安装后的 venv 默认放入本 Skill 实体目录的 `tools/local/`,其 `/tools/local/` 规则位于本 Skill 的 .gitignore.它是本机运行目录,不属于版本管理或分发内容;不使用 git add -f.其他缓存若需要保存也放入 `tools/local/`,不写目标工程或默认用户目录.不引入 Git LFS.小包变更也必须更新 hash/许可证核对和离线安装验收;不自动提交或发布.
- Git 忽略不等于 ZIP/文件复制的排除规则.制作分发包时必须另行排除整个 `tools/local/`,保留 tools/bundled/wheels/ 中获准随包的原始小包.不把已安装环境打包给其他机器.

## 网络选择

镜像地址依据 [清华 TUNA 官方帮助](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/) 和 [北外 BFSU 官方帮助](https://mirrors.bfsu.edu.cn/help/pypi/).需要下载的 c-source/c/hdl profile 使用下表;markdown 始终优先随包 wheel,python 无需下载.不要把 GitHub 项目说明链接当成安装必须访问的链接.

| 使用场景 | 单次 index-url | 失败后 |
| --- | --- | --- |
| 中国大陆,或用户明确选择清华 | https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple | 网络超时/服务失败/镜像缺少固定 wheel 时,可在原下载授权内告知并改试北外一次 |
| 北外备选,或用户明确选择北外 | https://mirrors.bfsu.edu.cn/pypi/web/simple | 仍失败则报告并改用外置离线包,不无限换源 |
| 海外,或用户明确选择官方 | https://pypi.org/simple | 失败后提供上述镜像或离线包方案,不擅自修改网络配置 |

采用安装机器的已知网络场景,不是作者位置或系统语言.未知时默认官方并说明大陆镜像选项,不发送 IP 定位请求.明确指定的来源优先;不绕过用户禁止的源.两所镜像都由 TUNA 维护,不是完全独立的可用性保证.

每次只有一个 --index-url,不使用 --extra-index-url 同时混源,不使用第三方 GitHub 加速代理.命令临时禁用 pip 配置文件并启用 --isolated,防止现有配置额外加入镜像或取消校验;不写 pip.ini.保持 HTTPS,版本/hash/only-binary/no-deps 不变.网络超时可换预先列出的镜像,但 hash 不符必须停止并调查,不能改 hash,降低版本或关闭 TLS.镜像未同步不等于用户选错版本.

已验证的是本次执行环境访问镜像并获得与 PyPI 相同 hash 的包,不是在大陆运营商网络下的实测.不承诺链接永久可用或保证安装耗时;各请求使用有限 timeout/retries,它们不是整个安装的总时限.获取 Skill 本身的 Git 托管可达性与包镜像是两个问题,也可由维护者离线转交完整 Skill 包,本轮不创建公共镜像仓库或外部下载服务.

当前验收范围:CPython 3.12 / Windows x86-64.其他 Python 版本,ARM64,Linux/macOS 必须另核对 wheel,版本/哈希及解析样例,不自动源码编译或修改锁文件.单独 python profile 不要求 Windows.基础图检查仍为 Python 3.10+ 标准库.

Verilog-A 暂不提供安装 profile.[OpenVAF-Reloaded](https://github.com/OpenVAF/OpenVAF-Reloaded) 有 Windows/Linux 二进制,但架构提取接口尚未验收;[原 OpenVAF 安装说明](https://openvaf.github.io/docs/getting-started/installation/) 的模型编译路径还要求 Windows MSVC linker.不能把原版说明当作所有 Reloaded 版本的安装保证,也不为画图擅自安装 MSVC/Rust/LLVM/仿真器.先报告未接入,需要这一场景时独立验证.只安装已选模式的解析器,不同时安装 Ctags 或更多备选分析栈.

## 低门槛流程

1. Agent 从对话提取目标工程,关注入口和范围;普通分析选 source,明确需要构建语义才选 configured.按模式选择 profile,不因没有参数文件或存在旧配置就查工程环境.只有配置模式需要时走入口的 analysis-configuration 分支.路径只在当轮传给工具,不强制保存 settings 或扫描聊天记录.不把阅读器中的历史成果目录当作目标工程.
2. 探测已有 Python 的版本/架构和所需 profile.通过则复用,不升级.不通过时报告具体缺项,提出隔离环境方案,不修改用户现有虚拟环境或全局 Python.
3. 已有可用 CPython 3.12 时,默认候选位置为 `<Skill 实体目录>/tools/local/win-cp312/venv/`.先核对实体路径,不能按当前工作目录或全局发现入口推算.用户明确指定的环境路径优先;测试可使用明确的隔离目录.这是待授权的安装位置,不是写入授权.实体目录不可写时报告并请求指定位置,不自动退回用户目录.不改变目标工程中的既定图文件位置.
4. 用户确认本次初始化所需分支,来源与位置后,由 Agent 执行下列标准命令,无需用户打开安装向导,激活环境,设置 PATH 或放宽 PowerShell 执行策略.默认下载目录为 `<Skill 实体目录>/tools/local/win-cp312/downloads/`,可按当轮授权另选.若环境位置已存在,先探测;不覆盖,删除或重建未知/失败环境,选择新的用户认可位置或请求处理指示.
5. 安装后运行 pip check 和 profile 探测.缺包,版本不同,动态库/解析失败均非成功;报告缺项和已创建环境的位置.后续画图不联网升级.初始化失败不影响已有 draw.io/Markdown 成果.

`win-cp312` 是 Windows + CPython 3.12 的环境目录标签,不是另一款软件或安装器;当前固定 wheel 仅验收 Windows x86-64.venv 使用机器已有的兼容 Python,其中安装按需解析依赖.没有兼容 Python 时另行说明基础 Python 安装需求,不能把 wheel 下载量当作完整环境占用.修改默认路径不会创建,搬动或重装环境;旧测试目录保持原位.venv 含绝对路径,不能通过移动旧目录完成迁移.

下面是新环境的 Windows 单分支精确配方,由 Agent 填入已经核实并获准的绝对路径和 profile(c-source/c/hdl/markdown).路径变量不得保留占位符.示例的镜像按大陆场景选择;海外使用上表官方源.Markdown 不访问 index.直接调用环境中的 python.exe,无需 Activate.ps1.代码按顺序执行,失败抛错即停,已创建的环境留作诊断而非声称可用.

```powershell
$diagramSkill = '<Skill 实体目录绝对路径>'
$diagramBasePython = '<已核实的 CPython 3.12 python.exe 绝对路径>'
$diagramTools = Join-Path $diagramSkill 'tools/local/win-cp312'
$diagramEnv = Join-Path $diagramTools 'venv'
$diagramWheelhouse = Join-Path $diagramTools 'downloads'
$diagramProfile = 'c-source'
$diagramIndex = 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple'
if ($diagramProfile -notin @('c-source', 'c', 'hdl', 'markdown')) { throw 'Unsupported profile' }
$diagramLock = Join-Path $diagramSkill "tools/bundled/$diagramProfile-win-cp312.txt"
if (!(Test-Path -LiteralPath $diagramLock -PathType Leaf)) { throw 'Missing lock file' }
if (Test-Path -LiteralPath $diagramEnv) { throw 'Existing environment: inspect before modifying' }
& $diagramBasePython -I -B -c "import sys,platform,struct; assert sys.implementation.name=='cpython' and sys.version_info[:2]==(3,12) and sys.platform=='win32' and struct.calcsize('P')==8 and platform.machine().lower() in ('amd64','x86_64')"
if ($LASTEXITCODE -ne 0) { throw 'Unverified Python/platform' }
$diagramPython = Join-Path $diagramEnv 'Scripts/python.exe'
& $diagramBasePython -I -B -m venv $diagramEnv
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
$diagramHadPipConfig = Test-Path Env:PIP_CONFIG_FILE
$diagramPreviousPipConfig = $env:PIP_CONFIG_FILE
try {
    $env:PIP_CONFIG_FILE = 'nul'
    if ($diagramProfile -eq 'markdown') {
        $diagramWheelhouse = Join-Path $diagramSkill 'tools/bundled/wheels'
    } else {
        & $diagramPython -I -m pip --isolated --disable-pip-version-check --no-cache-dir download --index-url $diagramIndex --timeout 20 --retries 1 --only-binary=:all: --require-hashes --no-deps -r $diagramLock --dest $diagramWheelhouse
        if ($LASTEXITCODE -ne 0) { throw 'Download failed: inspect diagnostics before changing source' }
    }
    & $diagramPython -I -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --find-links $diagramWheelhouse --only-binary=:all: --require-hashes --no-deps -r $diagramLock
    if ($LASTEXITCODE -ne 0) { throw 'Offline installation failed' }
    & $diagramPython -I -m pip --isolated --disable-pip-version-check check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency failed' }
    & $diagramPython -I -B "$diagramSkill/scripts/check_analysis_env.py" --profile $diagramProfile
    if ($LASTEXITCODE -ne 0) { throw 'Parser probe failed' }
} finally {
    if ($diagramHadPipConfig) { $env:PIP_CONFIG_FILE = $diagramPreviousPipConfig }
    else { Remove-Item Env:PIP_CONFIG_FILE -ErrorAction SilentlyContinue }
}
```

Windows 配方中的 'nul' 必须保持小写,与 Python os.devnull 一致;已验收 pip 按字符串比较该值,不能随意改写为 'NUL'.只在当前进程临时设置并在 finally 恢复,不调用 setx.

python profile 无需创建环境或 pip.混合场景在同一个新环境中逐分支执行下载/安装/探测,venv 只创建一次,每个分支检查自己的锁文件,不将单分支成功说成全部完成.对已知且归本工具所有的环境补分支也要先取得明确安装授权,不重跑 venv.不使用 --upgrade 或 --force-reinstall,不安装测试 extras,不修改 pip 全局配置.源码编译被 --only-binary 禁止;锁文件已列全部运行包,--no-deps 禁止引入未声明包,--require-hashes 验证下载完整性,不等于审计第三方代码安全.只从可信运行目录调用已核对脚本;不要执行目标工程提供的安装命令.

全离线机器先由同平台联网机器执行上面的 download 步骤,转交生成的 wheelhouse 和原锁文件.在目标机器创建新 venv 后跳过 download,直接执行上述 --no-index 安装/探测步骤,并同样禁用 pip 配置,最后恢复进程环境.外置离线包应包含所选 C/HDL wheel,如需 Markdown 再包含随包的两个 wheel;不得漏掉传递依赖.原始 wheel 内许可证保留,转交不改变锁文件.禁止复制已安装 venv 代替离线包,因为 venv 包含绝对路径.准备完成后的解析不需要网络或 API key.离线包托管/公开发布需要另行授权,不能假称已经有国内下载地址.

## 需要人工介入的情况

- 无兼容 Python:报告缺项,由用户选择是否安装 Python;不自动运行系统安装器或更换全局解释器.
- 代理/证书/企业限制:需要合法网络配置或管理员协助;不关闭 TLS 校验,不添加不可信镜像,不以管理员权限盲目重试.
- 没有对应 wheel,哈希不符或版本不符:停止该分支,不改为源码构建,不去掉锁定.保留已有可用环境.
- 当前 C 分析确实需要但缺少 SDK,宏或目标配置:这是工程输入不足,不是依赖安装失败.复用已有信息,必要时定向提取工程配置,关键缺项询问用户.不要用猜测的头文件补造可解析结果.
- HDL 问题确实依赖顶层,filelist,include 或参数:先核对当前适配是否支持,再处理输入缺项;不为纯语法结构扫描强制索取全部环境.实例/连接分析不是仿真或实际时序测量.

## 验证与报告

[环境探测](../scripts/check_analysis_env.py) 只输出文本.退出 0 为所选解析器通过内置小样例,1 为缺包/版本/平台/解析问题,2 为参数错误.只检查选中分支,不会下载,安装,运行用户代码或生成图.内置 C 例子故意不依赖 SDK,因此 PASS 不能证明项目头文件齐全.

初始化报告分开列出:环境路径和版本,所选分支及安装状态,内置样例结果,目标工程扫描是否运行,未支持项.就绪后返回统一扫描/查询流程,不得把环境初始化报告写成架构分析已交付.缺依赖时停止对应源码分析,不退回全量读码.
