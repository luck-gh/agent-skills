# HDL 与模拟行为模型

先确认语言,top/testbench,目标配置和问题范围.只读源码/已有构建说明,不为画图启动仿真,综合或安装 HDL 工具.

- Verilog/SystemVerilog:先识别 module/interface/package,实例层级,端口绑定,parameter/generate 和条件编译.区分设计模块与 testbench,不能把互斥 generate 分支同时画成活动实例.
- 接口说明记录端口方向,位宽/参数表达式,时钟/复位,valid-ready 或其他实际握手条件.参数不确定时保留表达式,不猜展开结果.未驱动端口,黑盒和省略实例明确标注.
- 分开组合逻辑与时序逻辑.always_ff/时钟沿与非阻塞赋值描述同一时钟事件下的状态更新,不能按代码行顺序画成逐模块同步调用.
- 时钟域交叉,复位极性/同步性,多驱动和跨域缓冲只有证据充分时才作事实描述.图形不能证明 CDC 安全,建立保持时间或综合后真实结构.
- SystemVerilog class/task/function,virtual interface 或 UVM 环境属于另一抽象层,只有问题涉及验证环境才展开;连接不等于消息已执行.
- Verilog-A:识别 analog block,discipline/nature,端口电气关系,参数和 contribution.如 `I(p,n) <+ ...` 表达模拟方程贡献,不是软件调用或逐句离散流程.连续量关系和事件控制分别解释,不伪造求解器顺序.

draw.io 展示实例/功能块与主要信号连接;Markdown 解释层级,端口表,配置条件和关键协议.用时序图说明协议交互时区分时钟拍与消息顺序,没有周期依据不得编造波形或精确延迟.模拟模型优先方程说明和依赖图,不强制套时序图.
