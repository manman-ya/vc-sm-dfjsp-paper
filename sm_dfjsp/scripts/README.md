# 脚本目录说明

本目录用于集中存放项目的可运行脚本。脚本主要负责调用
`src/smdfjsp/` 中的算法、模型、评价指标和绘图函数，完成数据构造、
实验运行、断点续跑、结果汇总、图表生成等任务。

核心算法源码不放在这里，而是在：

```text
src/smdfjsp/
```

## 目录分工

```text
scripts/       可运行脚本和实验入口
src/smdfjsp/   项目源代码、算法实现、模型评价、指标计算
tests/         单元测试和回归测试
data/          数据实例
reports/       实验输出、图片、指标表、排程结果
docs/          项目文档和实验说明
configs/       配置文件
```

## 主要 MVC 实验入口

- `run_mvc_mk13_moead_50iter.py`
  一句话运行 MK13 二目标实验。包含 NSGA-II、MOEA/D、MVC-EDATS。
  其中 MVC-EDATS 跑 50 代，并输出单链/跨链 selected 非支配解的甘特图、
  作业分配表和工序排程明细。

- `run_mvc_mk13_conflict_2obj_resumable.py`
  MK13 二目标实验的可续跑主脚本。支持进度条、断点续跑、只重建图片和汇总。

- `run_mvc_mk05_medium_2obj_resumable.py`
  MK05 二目标中等规模可续跑实验脚本。

- `run_mvc_single.py`
  对单个 MVC 实例运行一个算法，并生成 Pareto 图、甘特图、负载图等。

## MVC 辅助脚本

- `mvc_experiment_utils.py`
  MVC 实验共用工具，包括算法调度、CSV 读写、指标汇总、折中解选择等。

- `build_mvc_mk01_15.py`
  构造 MVC-MK01 到 MVC-MK15 数据集。

- `intensify_mk13_conflicts.py`
  增强 MK13 实例中的快贵/慢便宜、同链/跨链、负载均衡/跨链代价冲突。

- `validate_mvc_instances.py`
  检查 MVC 实例 JSON 的完整性和可行性。

- `build_mvc_figures.py`
  根据实验结果重新生成 MVC 图片。

- `build_mvc_tables.py`
  根据实验结果生成 MVC 指标表和对比表。

## 原始 SM-DFJSP 复现实验脚本

- `run_experiments_repeated.py`
  多算法重复实验。

- `run_ablation_repeated.py`
  消融实验。

- `tune_params_taguchi.py`
  Taguchi 参数调优。

- `visualize_repro_results.py`
  复现实验结果可视化。

- `plot_results.py`
  通用结果绘图脚本。

- `build_sdmk.py`
  构造 SDMK 数据。

- `build_sdmk_01_15_x2_r3r4.py`
  构造扩展版 SDMK01-15 数据。

- `validate_sdmk_dataset.py`
  校验 SDMK 数据集。

## 常用命令

在项目根目录 `sm_dfjsp/` 下运行：

```powershell
python scripts/run_mvc_mk13_moead_50iter.py
```

只查看运行计划，不真正运行实验：

```powershell
python scripts/run_mvc_mk13_moead_50iter.py --dry-run
```

实验已完成时，只重新生成图片和汇总：

```powershell
python scripts/run_mvc_mk13_moead_50iter.py --only-figures
```

如果实验中断，重新执行同一条运行命令即可续跑；脚本会跳过已经完成的 run。
