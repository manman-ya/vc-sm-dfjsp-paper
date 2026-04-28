# SM-DFJSP EDA-TS 算法映射文档

## 1. 范围
- 论文算法范围：EDA-TS，包括 PMA/PMS/PMM、多种群策略、TS 三类邻域、短期/长期记忆禁忌机制、非支配记忆机制。
- 代码基线：
  - `src/smdfjsp/eda_ts/algorithm.py`
  - `src/smdfjsp/baselines/*.py`（对比算法）

## 2. 状态说明
- `same`：机制意图已实现，基本一致。
- `approx`：机制意图已实现，但过程细节与论文伪代码存在差异。
- `missing`：未发现显式实现。

## 3. EDA-TS 步骤映射

| 论文组件 | 代码证据 | 状态 | 说明 |
|---|---|---|---|
| 四层编码（UA/OS/OP/MS） | `core/encoding.py:106`, `core/encoding.py:175` | `same` | 已有完整编码与修复流程。 |
| PMA/PMS/PMM 概率矩阵 | `algorithm.py:62-95` | `same` | 三类概率矩阵显式初始化。 |
| 代际多种群策略 | `algorithm.py:210-232` | `same` | UA: sampling/MD；MS: sampling/MC/MCT。 |
| PMA/PMS/PMM 更新 | `algorithm.py:254-321` | `approx` | 采用精英频率学习，非论文符号级逐行复刻。 |
| TS 邻域 I（作业重分配） | `algorithm.py:321-343` | `same` | 已实现基于兼容集合的 SRU 迁移。 |
| TS 邻域 II（OS 插入） | `algorithm.py:345-370` | `same` | 已实现 OS 序列插入操作。 |
| TS 邻域 III（MS 替换） | `algorithm.py:372-385` | `same` | 已实现工序机器替换。 |
| 短期禁忌表 | `algorithm.py:483`, `algorithm.py:551` | `approx` | 已升级为 move 级 tabu key（N1/N2/N3），但是否与论文动作编码逐项同构仍需进一步对拍。 |
| 长期记忆惩罚（LMLS/LMLM 意图） | `algorithm.py:514`, `algorithm.py:532`, `algorithm.py:561` | `approx` | 已按邻域动作触发记忆（N1->LMLS，N3->LMLM），粒度明显优于旧实现，但尚未形成论文步骤号级证明。 |
| 非支配记忆池 | `algorithm.py:454-506` | `same` | 已实现外部 ND 池与迭代融合。 |
| EDA/TS 协同迭代 | `algorithm.py:449-506` | `same` | 已实现 EDA 生成 + TS 局部强化。 |
| 终止条件（max_iter/time_limit） | `algorithm.py:460-462` | `same` | 两类终止条件均已实现。 |
| PMA/PMS/PMM 审计追踪 | `algorithm.py:42`, `algorithm.py:93`, `algorithm.py:599` | `same` | 已支持 `trace_enabled/trace_dir/trace_every` 的迭代快照输出（jsonl）。 |

## 4. 对比算法映射

| 论文对比算法 | 代码证据 | 状态 | 说明 |
|---|---|---|---|
| EDA | `baselines/eda.py` | `approx` | 通过关闭 TS/多种群/ND 记忆获得的工程变体。 |
| NSGA-II | `baselines/nsgaii.py` | `approx` | 功能实现存在，但未完成文献算子级同构审计。 |
| EDA-VNS | `baselines/eda.py`（`run_eda_vns`） | `approx` | 作为统一框架下配置化变体实现。 |
| H-GA-TS | `baselines/h_gats.py` | `approx` | GA 主干 + TS 辅助的工程等价实现。 |

## 5. 严格复现差距
1. PMA/PMS/PMM 的采样与更新仍需与论文伪代码步骤号逐条对拍。
2. tabu-key 与 LMLS/LMLM 虽已 move 化，但仍需形成“论文条款级一一映射证明”。
3. 对比算法需要独立完成参数/算子与原始文献的一致性审计。

## 6. 建议补充的可审计能力
1. 在现有 trace 基础上，补充邻域接受/拒绝率、tabu 命中率统计。
2. 增加“论文步骤号 -> 代码输出字段”的自动对拍报告。
3. 保留确定性种子回归测试（`tests/` 已具备）用于防漂移。
