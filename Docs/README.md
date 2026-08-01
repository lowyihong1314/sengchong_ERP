# ERP Upgrade Docs

这些文档是根据当前 ERP 代码和 AutoCount SQL 数据库只读检查整理出来的升级规划。

检查日期：2026-06-05  
检查范围：`AED_SENG`, `AED_MANSON`  
目标：让这个 Web ERP 覆盖你日常最常用的 AutoCount 功能，同时保持 AutoCount 作为正式会计数据源。

## 文档列表

- [Business Context](./business-context.md)
  - 根据 `sengchong/` 官网和实际室内设计/木工定制业务调整的 ERP 方向。
- [AutoCount DB Findings](./autocount-db-findings.md)
  - 当前数据库里真正有数据的模块、数量、金额、报表模板、编号格式。
- [Data Mapping](./data-mapping.md)
  - Web ERP 模块和 AutoCount 表之间的对应关系。
- [Sengchong Website Ownership](./sengchong-website-ownership.md)
  - `sengchong.com` 只负责公开渲染，官网内容、项目图片和发布权限全部由 ERP 管理。
- [Website Next Steps](./website-next-steps.md)
  - Bank reconciliation 后继续深入 website 的执行顺序。
- [ERP Upgrade Roadmap](./erp-upgrade-roadmap.md)
  - 分阶段升级路线，按业务价值和风险排序。
- [Module Specs](./module-specs.md)
  - 每个模块应该具备的页面、按钮、动作和打印功能。
- [Implementation Rules](./implementation-rules.md)
  - 以后开发这个 ERP 必须遵守的技术规则，避免破坏 AutoCount 数据。

## 核心判断

`sengchong/` 显示业务不是普通 retail，而是室内设计 / 家私 / 木工定制项目。`AED_MANSON` 是目前更活跃的公司库。销售、AR payment、AP invoice、AP payment、stock movement、GL 都已经有数据，所以 ERP 不能只做 invoice/quotation；下一阶段最值得升级的是：

1. Project / Job layer，把 quotation、invoice、AR payment、supplier cost、照片串起来
2. AP / Supplier / Creditor 模块，用来追材料和 subcontractor 成本
3. AR collection：aging、statement、payment request、official receipt
4. Bank / Cashbook / Payment method 模块，分 CIMB/DBS/MBB/PayNow 等收付款
5. Stock movement / material inquiry
6. Sengchong website content ownership：官网只渲染，内容和项目图片发布从 ERP 控制
7. Report template selector and batch printing
