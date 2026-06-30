# MVC-SM-DFJSP 20 随机种子严谨实验运行说明（Linux）

## 1. 实验设计

统一使用 20 个随机种子：`20260428` 至 `20260447`。脚本顺序执行以下实验：

1. 固定迭代次数：4 种算法、cross-off/on、15 个实例、20 个种子。
2. 等 CPU 时间：每次运行使用相同进程 CPU 时间上限，候选解评价和局部搜索内部均检查截止时间。
3. 等函数评价次数（FE）：初始化、种群采样、基线算法子代和禁忌局部搜索的目标函数调用全部计入统一预算。
4. 配对消融：A0 Full 与 A1-A5 在相同实例、相同种子、相同 FE 预算下比较。
5. 自动分析：单实例均值、样本标准差、95% Student-t 置信区间，配对 Wilcoxon 检验和 Holm 校正，收敛曲线及模块运行时间。

固定迭代结果用于与旧实验衔接。论文中的公平性主结论应优先使用等 CPU 时间和等 FE 两组结果。等 CPU 时间阶段通过 `--time-measure cpu` 使用 Python `time.process_time()`，消除 cross-on 和局部搜索在单代中额外耗时造成的比较偏差；等 FE 则隔离“更多目标函数调用”带来的优势。两组结果同时报告，才能区分搜索质量和计算开销。

## 2. 环境准备

在项目根目录执行：

```bash
cd /path/to/vc-sm_dfjsp/sm_dfjsp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

确认 15 个 JSON 实例位于：

```text
data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc/
```

## 3. 完整运行

```bash
bash scripts/run_mvc_rigorous_20seeds_linux.sh
```

后台运行并保存日志：

```bash
nohup bash scripts/run_mvc_rigorous_20seeds_linux.sh \
  > rigorous_20seeds.log 2>&1 &
tail -f rigorous_20seeds.log
```

每个 Python 实验命令显示“已完成运行数/总运行数”进度条。外层脚本显示 5 个阶段的进度。

## 4. 中断后继续

直接重新执行同一命令：

```bash
bash scripts/run_mvc_rigorous_20seeds_linux.sh
```

外层脚本通过 `${OUT_ROOT}/.pipeline_state/*.done` 跳过完整阶段；阶段内部通过 `--resume` 检查每个“实例-算法-cross 模式-种子”的三个结果文件并跳过完整运行。中断时正在写入的单次运行最多只需重算一次。

若需要重跑某一完整阶段，删除对应标记，例如：

```bash
rm reports/mvc_mk01_15_integrated_mechanism_equalproc_rigorous_20seeds/.pipeline_state/02_equal_cpu_time.done
bash scripts/run_mvc_rigorous_20seeds_linux.sh
```

已有单次运行仍会被 `--resume` 跳过。要重算某个单次运行，应只删除该运行在 `raw/` 和 `pareto/` 下对应的 CSV 文件。

## 5. 参数覆盖

所有主要参数均可用环境变量覆盖：

```bash
CPU_TIME_LIMIT=900 \
FE_BUDGET=20000 \
POPSIZE=80 \
OUT_ROOT=reports/my_rigorous_run \
bash scripts/run_mvc_rigorous_20seeds_linux.sh
```

常用变量：

| 变量 | 默认值 | 含义 |
| --- | ---: | --- |
| `POPSIZE` | 80 | 种群规模 |
| `FIXED_MAX_ITER` | 150 | 固定迭代实验迭代数 |
| `CPU_TIME_LIMIT` | 600 | 等 CPU 时间实验每次运行秒数 |
| `FE_BUDGET` | 12000 | 等 FE 和消融实验每次运行评价预算 |
| `SAFETY_TIME_LIMIT` | 12000 | 等 FE 实验异常运行保护上限（秒） |
| `OUT_ROOT` | 见脚本 | 总输出目录 |
| `INPUT_DIR` | 见脚本 | 实例目录 |

不要在同一批正式实验中途修改参数。若修改预算或种子，应使用新的 `OUT_ROOT`，防止 `--resume` 混用不同实验条件。

## 6. 关键输出

最终分析位于 `${OUT_ROOT}/analysis/`：

- `per_instance_mean_std_ci95.csv`：每个实例、算法和 cross 模式的均值、样本标准差及 95% CI。
- `ablation_paired_wilcoxon_holm.csv`：A0 与各消融变体的总体和逐实例配对检验、Holm 校正、胜负次数及效应量。
- `convergence_by_instance.csv`：逐实例收敛统计。
- `convergence_normalized_aggregate.csv`：实例内归一化后汇总的收敛统计。
- `figures/convergence_*.png` 和 `.pdf`：固定迭代、等 CPU 时间、等 FE 收敛曲线及 95% CI。
- `module_runtime_mean_std_ci95.csv`：初始化、采样/评价、局部搜索、档案选择等模块耗时统计。

`igd` 为基于实例内共同参考前沿和目标范围的归一化 IGD；`raw_igd` 仅作为量纲诊断值保留。函数评价次数不包含实验结束后为导出 Pareto 明细而进行的诊断性重算，因为该重算不参与搜索决策。
