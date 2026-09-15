# Damper Test Data Analyzer

[![Tests](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer/actions/workflows/tests.yml/badge.svg?branch=dev-v0.5-i18n)](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer/actions/workflows/tests.yml)
[![Build Windows EXE](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer/actions/workflows/build-windows.yml/badge.svg?branch=dev-v0.5-i18n)](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer/actions/workflows/build-windows.yml)

富奥东机工减振器有限公司（FAWER-TOKICO SHOCK ABSORBER CO., LTD.）CDC / 电控减振器台架数据分析工具。

- 编制：研发院技术中心　李振海
- 发布日期：2026/9/7
- 发布：第1版
- 当前功能版本：`V0.9.0`
- Python package version：`1.0.0`
- GitHub 仓库：[lizhenhai2024-alt/Damper-Test-Data-Analyzer](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer)

## 核心功能

- MTS `.dat` 重复 `Data Acquisition` 数据块解析
- CSV / XLSX 导入
- CDC 反馈电流自动归一到 0.1 A，并保留实际中位值/标准差
- Run 分段、升/降电流 Sweep 标记
- 基于位移运动方向的复原/压缩识别
- 完整 Cycle 检测，不把 Block 与 Cycle 直接等同
- Audi：最后一个完整循环 + 行程中心总行程 10% 窗口 + 复原最大值 / 压缩最小值
- Window Mean：窗口比例可设置，基准固定为总行程全宽
- Zero Crossing：目标位移线性插值
- 气体反弹力支持“加上 / 减去”恒定修正，原始载荷永不覆盖
- 响应分析提供 BMW、Audi、红旗、国内主机和零跑预设；红旗速度为 0.131/0.262/0.524/1.047 m/s，国内主机为 0.1/0.3/0.6 m/s，零跑为 0.15/0.70 m/s。目标速度仍可手动输入任意正有限值。
- 响应时间以用户设置的电流触发比例交点为零点；电流图的 I 下标随触发比例变化并定位在实际触发交点。起始载荷阈值默认 F₁%，可调整；t 起始响应时间使用相同下标。
- F 起始阈值与 F₆₃% 可分别勾选是否在阻尼力图中显示；关闭后对应水平线、竖直响应线和时间文字同步隐藏。F₉₀% 与 F₁₀₀% 始终显示。
- 响应图采用与轴标题同号的正常字重透明标注；载荷阈值标签位于左侧，参考虚线连续；竖虚线与实测曲线交点加圆点，载荷响应时间交替分布于曲线两侧。
- 响应图可切换为双 Y 轴 I₁₀%→F₉₀% 模式：X 轴为时间，左轴及蓝色曲线为电流，右轴及红色曲线为阻尼力；两条竖虚线标记电流 I₁₀% 与阻尼力 F₉₀% 的线性插值时刻。电流曲线只标记 I₁₀% 交点，阻尼力曲线标记两个时刻的交点；不显示 F₉₀% 时刻的电流交点和文字。主响应时间为 `t(F₉₀%) − t(I₁₀%)`，与三联响应图一致。
- Summary / Run / Cycle 三级结果
- Data Quality：按 acquisition block 输出采样点数、采样率、时间间隔、位移范围、载荷范围、电流中位数/标准差及结构性异常
- GUI 分析前执行 Data Quality preflight；结构性 `Invalid` 输入停止分析
- Sweep Comparison：保留 Up / Down 结果并输出 `Delta = Down - Up`
- X 轴字段自由选择、Y 轴多字段选择
- Current / Run / Cycle 图形筛选
- 不同量纲自动上下分图并共享 X 轴
- Audi 10% 评价窗口与复原/压缩峰值点可视化
- 图形背景：白色、黑色、浅灰、深灰及自定义颜色
- 图形工具：放大、缩小、框选放大、平移、恢复、滚轮缩放
- 中文 / English 界面实时切换，**默认中文**
- 专业帮助页面：使用流程、评价算法、符号约定、气体力修正、Data Quality、Sweep、图形工具、常见问题及工程边界
- `.xlsx` 与 PNG 导出；菜单栏可选 150 / 300 / 600 PPI，默认 300 PPI。PNG 为无损位图，清晰度由导出像素尺寸与查看比例决定；打印或裁切请选择 600 PPI，并按 100% 比例检查原图。
- Windows x86-64 单文件 EXE 自动构建

## V0.9.0 Audi 第20/21项与 PVP/DCTW 批量分析

- 新增“Audi 第20/21项”页面：第20项计算不同电流下的归一化阻尼力、电流—力线性拟合 R² 和最大偏差；第21项按速度与压缩/复原方向计算硬—软阻尼力范围和放大倍数。
- 支持 MTS Shock `.PVP` 和 CTW Probe `.dctw`。PVP 可从一个文件读取多个速度段；DCTW 使用文件内 Bond 压缩数据、通道定义及力传感器标定表，直接换算为 N，无需先由试验软件导出 CSV。
- 可一次选择多个文件，也可递归扫描文件夹及全部子文件夹。程序从 `0.4.pvp`、`2#-0.3A-1.dctw` 等文件名识别电流，列表中的电流允许人工修正。
- 文件列表支持多选“移除所选数据”，只从当前分析中排除重复或异常测量，不删除磁盘原文件。同电流、速度和方向的保留重复测量取均值，并在结果中保存重复次数和标准差。
- 仅使用不高于 1.047 m/s 的速度段；每个速度段取最后一个完整循环，在中心总行程 10% 窗口分别评价复原最大力和压缩最小力。
- Excel 导出包含第20项、第21项、运行明细、源文件和计算设置五个工作表。

## V0.8.21 双 Y 轴阻尼力响应、客户速度预设与迟滞数据导入

- 自动适配 100% / 150% DPI，工具栏换行，小屏幕可滚动查看完整响应图。
- 迟滞首图为电流—阻尼力共轴图，纵轴为“压缩<--阻尼力(N)-->复原”。
- 所有迟滞试验曲线统一使用连续实线段；取消数据点符号并强制连接相邻工况点，避免曲线在正常缩放下呈现断续或虚线外观。速度、电流和方向通过颜色与图例区分。
- 迟滞分析中的阻尼力统一按整数显示和导出，内部计算继续保留完整精度。
- 按实测速度独立计算迟滞，默认速度分组容差 3%，不跨速度配对或求平均。
- 可选择单一速度的电流—阻尼力迟滞图，或单一电流的速度—阻尼力图；Excel 包含全部图，PNG 导出当前图。
- 增加电流—迟滞力柱状图，按速度和压缩/复原方向分组，柱顶直接显示整数迟滞力值。
- 可一次选择多个速度试验文件，程序隔离各文件的 Block ID 后统一进行实测速度分组。
- PNG 和 Excel 导图前自动激活迟滞图形页并设置完整纵轴范围，压缩方向不会被裁切。
- 导入新数据后，图形的 X/Y 轴列表只显示原始文件中实际存在且含有效数值的通道列；不显示 Block ID、Source Row、分析派生列或全空列。默认使用第 1 个通道作为 X 轴，其余通道作为 Y 轴。
- Y 轴已选字段文字使用对应曲线颜色，选择变化后自动同步。
- 载荷阈值标签保持与水平虚线相同的垂直顺序：负压缩行程 F₁% → F₆₃% → F₉₀% → F₁₀₀% 从上到下，正复原行程顺序从下到上。
- 主界面“评价设置 → 评价方法”仅保留“窗口均值”和“目标位移穿越插值”，默认使用“窗口均值”；响应时间与迟滞页面继续保留各自的 BMW/Audi 客户规范选择。
- 窗口基准固定为“总行程全宽”并隐藏该固定控件；窗口比例仍可设置。
- 迟滞数据可一次选择多个文件，也可选择一个文件夹并递归扫描全部子文件夹中的 `.dat` 文件。
- 详细使用说明见 [V0.9.0 使用说明](docs/V0.9.0_USER_GUIDE.md)。

## 数据质量原则

质量模块只对可客观判断的数据结构问题给出 Warning / Invalid，例如：

- 必需通道出现 NaN / Inf
- 时间戳不递增或重复
- 数据点过少
- 相邻采样时间出现明显大间隙

采样频率、位移步长以及升/降电流差异同时作为工程诊断指标输出，但在没有客户限值时不擅自判定合格/不合格。

## 安装开发环境

```bash
git clone https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer.git
cd Damper-Test-Data-Analyzer
python -m pip install -e ".[dev,gui]"
pytest -q
cdc-analyzer-gui
```

Windows 单文件 EXE 由 [Build Windows EXE](https://github.com/lizhenhai2024-alt/Damper-Test-Data-Analyzer/actions/workflows/build-windows.yml) 工作流自动构建，可在成功运行记录的 Artifacts 中下载。EXE 与 Artifact 文件名均包含软件版本，例如 `Damper_Test_Data_Analyzer_V0.9.0.exe`。

## CLI 示例

Audi 原始载荷：

```bash
cdc-analyzer sample.dat --profile audi
```

气体力修正后评价：

```bash
cdc-analyzer sample.dat --profile audi --gas-force 200 --gas-operation subtract --corrected --export result.xlsx
```

2% 单边振幅窗口均值：

```bash
cdc-analyzer sample.dat --profile window_mean --window-percent 2 --window-basis amplitude
```

## 重要约定

- 复原：`dX/dt > 0`，载荷期望 `> 0`
- 压缩：`dX/dt < 0`，载荷期望 `< 0`
- 电流工况标签显示保留 1 位小数
- 复原/压缩载荷结果显示保留整数 N
- 其它连续量显示保留 2 位小数
- 显示舍入不改变内部计算精度
- 气体力运算可选择 `Corrected Axial Load = Analysis Axial Load - Gas Force` 或 `Corrected Axial Load = Analysis Axial Load + Gas Force`
- Audi 10% 是评价窗口总宽度，即中心两侧各 `±5% × Total Stroke`
- Sweep Comparison 的 `Delta` 定义为 `Down - Up`
- Sweep 差异只做描述性输出，除非后续提供明确工程或客户限值
- `t₉₀%限值` 为项目可选限值；未设置时只报告测量值，不自动判定合格性

详细需求见 `docs/V1.0_REQUIREMENTS.md`；基础实测验证见 `docs/VALIDATION_2026-09-07.md`；V0.4 验证见 `docs/VALIDATION_V0.4_2026-09-07.md`。

V0.8.4 历史绘图规则保留于 [V0.8.4 绘图规则](docs/V0.8.4_RESPONSE_MARKER_LAYOUT.md)。
