# SM-DFJSP 复现报告（阶段 D 草案）

## 1. 报告信息
- 项目：SM-DFJSP 复现
- 论文：*Shared manufacturing-based distributed flexible job shop scheduling with supply-demand matching*（C&IE 189, 2024, 109950）
- 报告日期：2026-04-28
- 本草案范围：阶段 D 交付（映射文档 + 测试 + 审计结构），不等同于论文全口径大规模实验复现。

## 2. 一致性概览
- 总体状态：`partial`（部分一致）
- 原因：
  - 核心算法与评估流水线已实现并可运行。
  - 论文级严格复现要求（SDMK01-25 + G01/G02/G03 + 全表格产物）尚未全部完成。

## 3. 阶段 D 交付清单
- [x] 公式映射文档：`docs/MODEL_EQ_MAPPING.md`
- [x] 算法映射文档：`docs/ALGO_MAPPING.md`
- [x] 单元测试（约束 + 行为回归）：`tests/`
- [x] 本报告草案：`docs/REPRO_REPORT.md`

## 4. 表/图可追溯矩阵（当前）

| 论文产物 | 当前状态 | 说明 |
|---|---|---|
| Table 5（G01/G02/G03 上 EDA-TS vs Gurobi） | `not reproduced` | 缺少 G01/G02/G03 数据与求解器验证闭环。 |
| Table 7/8 | `partial` | 脚本已具备，当前结果以单实例 quick 口径为主。 |
| Table 9/10 | `partial` | Wilcoxon 函数已实现，但论文规模实例与重复次数尚未完成。 |
| Table 11/12/13 | `partial` | 消融脚本已具备，论文口径全量执行待完成。 |
| Table 14/15 | `not reproduced` | 案例研究数据与重建流程尚未到位。 |
| Fig. 10/11 | `partial` | Taguchi 绘图链路存在，但实例与时间协议仍与论文有差异。 |
| 其他对比图 | `partial` | 仅在当前实验范围内可用。 |

## 5. 代码-论文映射引用
- 公式映射：`docs/MODEL_EQ_MAPPING.md`
- 算法映射：`docs/ALGO_MAPPING.md`

## 6. 验证入口
- 约束/行为测试：
  - `python -m unittest discover -s tests -p "test_*.py"`
- 复现流程（当前范围）：
  - `python scripts/repro_mk01_15.py --mode quick`
  - `python scripts/repro_mk01_15.py --mode full`

## 7. 已知偏差（若要“严格复现”必须闭环）
1. 实例覆盖缺口：缺 SDMK16-25，缺 G01/G02/G03。
2. Taguchi 协议缺口：论文使用 SDMK17，且每组合 30 次、每次 100s。
3. 公式符号级同构与逐式可执行审计仍未完全闭环。
4. 论文级全表格产物尚未实现一键重建。

## 8. 当前判定
- 现阶段建议标注为：
  - `engineering reproduction with partial paper-level alignment`（工程复现，论文级部分对齐）
- 现阶段不应标注为：
  - `strict full replication of the paper`（严格完整复现）。
