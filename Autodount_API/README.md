# AutoCount API Integration Notes

这份说明用于 ERP 连接 AutoCount Accounting 2.2，重点覆盖 `AR Invoice`、`Quotation`、`Item`。原则是：ERP 不直接 SQL 查询或更新 AutoCount 表；SQL Server 资料只作为 AutoCount `DBSetting` 的连接配置，业务资料一律通过 AutoCount SDK / API 对象读取和保存。

## 集成边界

- 可以使用 SQL Server 资料建立 `AutoCount.Data.DBSetting`。
- 可以使用 AutoCount 用户建立 `AutoCount.Authentication.UserSession`。
- 读取、创建、编辑、删除业务单据时，使用 AutoCount 提供的 command / data access class。
- 不在 ERP 里写 `SELECT * FROM ARInvoice`、`UPDATE Item`、`INSERT INTO ...` 这类直接 SQL。
- 不绕过 AutoCount 的编号、税额、rounding、access right、approval、posting 和库存逻辑。
- ERP 端保存自己的外部单号，例如 `erp_order_id`、`erp_quote_id`，再映射 AutoCount 的 `DocNo` / `DocKey`。

## 本机环境

AutoCount DLL 位置：

```text
C:\Program Files\AutoCount\Accounting 2.2
```

Seng Chong 账套：

```text
Database: AED_SENG
Company: SENG CHONG INTERIOR DESIGN
AutoCount user: ADMIN
```

实际密码和 SQL 连接资料不要写进代码仓库。开发时从环境变量、Windows Credential Manager、`.env.local` 或部署平台 secret 读取。

## 必要引用

常用 DLL：

```text
AutoCount.dll
AutoCount.Accounting.dll
AutoCount.MainEntry.dll
AutoCount.ARAP.dll
AutoCount.Invoicing.dll
AutoCount.Sales.dll
AutoCount.Stock.dll
AutoCount.StockMaint.dll
```

AutoCount 2.1 之后，Sales / Purchase 的 DLL 名称有调整，但 namespace 多数仍保留在 `AutoCount.Invoicing.Sales`。以本机 2.2 SDK 为准。

## Login Flow

ERP 每次调用 AutoCount 前，先建立 `DBSetting` 和 `UserSession`。`DBSetting` 内部会连接 SQL Server，但 ERP 不应该用它执行自写 SQL 查业务表。

```csharp
using AutoCount.Authentication;
using AutoCount.Data;

public static UserSession LoginAutoCount(
    string serverName,
    string sqlUser,
    string sqlPassword,
    string dbName,
    string autoCountUser,
    string autoCountPassword)
{
    var dbSetting = new DBSetting(
        DBServerType.SQL2000,
        serverName,
        sqlUser,
        sqlPassword,
        dbName);

    var userSession = new UserSession(dbSetting);

    if (!userSession.Login(autoCountUser, autoCountPassword))
        throw new InvalidOperationException("AutoCount login failed.");

    return userSession;
}
```

建议 ERP 封装一个 `AutoCountClient`，让上层业务只调用 `CreateARInvoice()`、`GetQuotation()`、`UpsertItem()`，不要让业务模块直接碰 AutoCount SDK 细节。

## AR Invoice

用途：ERP 要创建财务 A/R 发票，或读取 AutoCount 里的 AR invoice 状态、金额、outstanding。

主要 class：

```text
AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess
AutoCount.ARAP.ARInvoice.ARInvoiceEntity
AutoCount.ARAP.ARInvoice.ARInvoiceDTLEntity
```

### 读取 AR Invoice

```csharp
using AutoCount.ARAP.ARInvoice;

public ARInvoiceEntity GetARInvoice(UserSession session, string docNo)
{
    var cmd = ARInvoiceDataAccess.Create(session, session.DBSetting);
    var doc = cmd.GetARInvoice(docNo);

    if (doc == null)
        throw new InvalidOperationException($"AR Invoice not found: {docNo}");

    return doc;
}
```

常用 header 字段：

```text
DocKey
DocNo
DocDate
DueDate
DebtorCode
Description
CurrencyCode
CurrencyRate
Total
Tax
NetTotal
PaymentAmt
Outstanding
Cancelled
DocStatus
```

常用 detail 字段：

```text
Seq
AccNo
Description
Amount
TaxCode
TaxRate
Tax
TaxAdjustment
SubTotal
NetAmount
ProjNo
DeptNo
```

### 创建 AR Invoice

```csharp
using AutoCount.ARAP.ARInvoice;
using AutoCount.Document;

public string CreateARInvoice(UserSession session)
{
    var cmd = ARInvoiceDataAccess.Create(session, session.DBSetting);
    var doc = cmd.NewARInvoice();

    doc.DebtorCode = "300-U001";
    doc.DocNo = "<<New>>";
    doc.DocDate = DateTime.Today;
    doc.Description = "ERP invoice";
    doc.CurrencyRate = 1m;
    doc.JournalType = "SALES";
    doc.RoundingMethod = DocumentRoundingMethod.LineByLine_Ver2;
    doc.InclusiveTax = false;

    var dtl = doc.NewDetail();
    dtl.AccNo = "500-0000";
    dtl.Description = "Service charge";
    dtl.Amount = 100m;
    dtl.TaxCode = null;
    dtl.ProjNo = DBNull.Value;
    dtl.DeptNo = DBNull.Value;

    cmd.SaveARInvoice(doc, session.LoginUserID);
    return doc.DocNo;
}
```

注意：

- `AccNo` 是 sales account，不可以是 debtor / creditor account。
- `NetTotal`、`Tax`、`Outstanding` 是 AutoCount 计算结果，不要手动覆盖。
- `ProjNo` / `DeptNo` 没有值时，用 `DBNull.Value` 或保留空值，不要写空字符串。
- 保存失败时捕捉 `AutoCount.AppException`，把 message 写入 ERP 同步日志。

## Quotation

用途：ERP 把报价单写入 AutoCount，或读取 AutoCount 报价单给 ERP 后续转 Sales Order / Invoice。

主要 class：

```text
AutoCount.Invoicing.Sales.Quotation.QuotationCommand
AutoCount.Invoicing.Sales.Quotation.Quotation
AutoCount.Invoicing.Sales.Quotation.QuotationDetail
```

### 创建 Quotation

```csharp
using AutoCount.Document;
using AutoCount.Invoicing.Sales.Quotation;

public string CreateQuotation(UserSession session)
{
    var cmd = QuotationCommand.Create(session, session.DBSetting);
    var doc = cmd.AddNew();

    doc.DebtorCode = "300-U001";
    doc.DocNo = "<<New>>";
    doc.DocDate = DateTime.Today;
    doc.Description = "ERP quotation";
    doc.CurrencyRate = 1m;
    doc.Agent = "ADMIN";
    doc.RoundingMethod = DocumentRoundingMethod.LineByLine_Ver2;
    doc.InclusiveTax = false;
    doc.Transferable = true;

    var dtl = doc.AddDetail();
    dtl.ItemCode = "00001";
    dtl.Description = "Wood Board";
    dtl.Qty = 1m;
    dtl.UOM = "pcs";
    dtl.UnitPrice = 392m;
    dtl.Discount = "";
    dtl.TaxCode = null;

    doc.Save();
    return doc.DocNo;
}
```

常用 header 字段：

```text
DocKey
DocNo
DocDate
DebtorCode
DebtorName
Description
CurrencyCode
CurrencyRate
Agent
NetTotal
FinalTotal
Tax
DocStatus
Cancelled
Transferable
IsTransfered
YourRef
Validity
PaymentTerm
DeliveryTerm
Remark1..Remark4
```

常用 detail 字段：

```text
ItemCode
Description
FurtherDescription
Location
Qty
UOM
UnitPrice
Discount
SubTotal
TaxCode
TaxRate
Tax
ProjNo
DeptNo
```

注意：

- 如果 Quotation 要被转 Sales Order / Invoice，需要确认 AutoCount 用户有 automatic approve quotation 的权限，否则保存后可能是等待批准状态。
- `ItemCode` 一旦指定，AutoCount 会根据 item / item group 带出默认 description、UOM、account、price、tax 等逻辑。
- ERP 不要自己计算最终税额作为权威值，保存后再读取 AutoCount 返回的 `FinalTotal` / `Tax`。

## Item

用途：ERP 同步产品资料、售价、UOM；或从 AutoCount 读取 item 作为 ERP 商品主数据。

本机 AutoCount 2.2 可用 class：

```text
AutoCount.Stock.Item.OldItem.StockItemMaintenance
AutoCount.Stock.Item.ItemCodeHelper
```

虽然 namespace 有 `OldItem`，但本机 2.2 SDK 仍提供该维护 API。它通过 DataSet / DataTable 保存 item，仍属于 AutoCount SDK 路径，不是 ERP 自己 SQL 写表。

### 读取 Item

```csharp
using AutoCount.Stock.Item.OldItem;

public DataRow GetItem(UserSession session, string itemCode)
{
    var cmd = StockItemMaintenance.Create(session, session.DBSetting);
    cmd.EditItem(itemCode);

    if (cmd.ItemTable.Rows.Count == 0)
        throw new InvalidOperationException($"Item not found: {itemCode}");

    return cmd.ItemTable.Rows[0];
}
```

常用 `ItemTable` 字段：

```text
ItemCode
Description
Desc2
FurtherDescription
ItemGroup
ItemType
ItemBrand
ItemClass
ItemCategory
BaseUOM
SalesUOM
PurchaseUOM
ReportUOM
StockControl
HasSerialNo
HasBatchNo
TaxCode
PurchaseTaxCode
IsActive
Discontinued
IsSalesItem
IsPurchaseItem
IsPOSItem
IsRawMaterialItem
IsFinishGoodsItem
MainSupplier
Classification
TotalBalQty
```

常用 `ItemUOMTable` 字段：

```text
ItemCode
UOM
Rate
Price
Cost
RealCost
MostRecentlyCost
MinSalePrice
MaxSalePrice
BarCode
Price2..Price6
Weight
WeightUOM
Volume
VolumeUOM
```

### 创建或更新 Item

```csharp
using AutoCount.Stock.Item.OldItem;

public void UpsertItem(UserSession session, string itemCode)
{
    var cmd = StockItemMaintenance.Create(session, session.DBSetting);

    if (cmd.QueryItemCode(itemCode))
        cmd.EditItem(itemCode);
    else
        cmd.NewItem();

    var item = cmd.ItemTable.Rows[0];
    item["ItemCode"] = itemCode;
    item["Description"] = "ERP item";
    item["BaseUOM"] = "pcs";
    item["SalesUOM"] = "pcs";
    item["PurchaseUOM"] = "pcs";
    item["IsActive"] = "T";
    item["Discontinued"] = "F";
    item["IsSalesItem"] = "T";
    item["IsPurchaseItem"] = "T";

    if (cmd.ItemUOMTable.Rows.Count == 0)
        cmd.InitialItemUOMNewRow(itemCode, "pcs", 1m);

    var uom = cmd.ItemUOMTable.Rows[0];
    uom["UOM"] = "pcs";
    uom["Rate"] = 1m;
    uom["Price"] = 392m;

    var result = cmd.Save(itemCode);

    if (!result.Success)
        throw new InvalidOperationException("Save item failed.");
}
```

注意：

- Item 的 boolean 字段很多是 `"T"` / `"F"` 字符串，不是 C# `bool`。
- 库存数量不要直接改 item table。库存调整请用 `StockAdjustmentCommand` 或 AutoCount 库存相关 API。
- 售价可以放在 `ItemUOMTable.Price`，多级售价常见为 `Price2` 到 `Price6`。
- UOM rate 改动可能会受已有交易限制，保存前要处理 AutoCount 抛出的异常。

## ERP 建议数据模型

ERP 端建议维护同步映射表：

```text
erp_entity_type   quotation | ar_invoice | item
erp_id            ERP 内部 ID
autocount_db      AED_SENG
autocount_doc_no  DocNo 或 ItemCode
autocount_doc_key DocKey，item 可为空
sync_status       pending | synced | failed
last_sync_at
last_error
```

建议同步流程：

1. ERP 建立或更新自己的业务资料。
2. 写入 `sync_status = pending`。
3. background worker 调 AutoCount SDK。
4. 成功后保存 AutoCount `DocNo` / `DocKey` / totals。
5. 失败时记录 `AutoCount.AppException.Message`，不要吞掉错误。
6. ERP 前端显示同步状态，让用户可以重试。

## 推荐封装

```text
AutoCountClient
  Login()
  CreateQuotation()
  GetQuotation()
  CreateARInvoice()
  GetARInvoice()
  UpsertItem()
  GetItem()

AutoCountSyncService
  SyncPendingQuotation()
  SyncPendingARInvoice()
  SyncPendingItem()
  RetryFailedJob()
```

每个写入动作要设计成 idempotent：

- ERP 先查自己的映射表，已有 `DocNo` 时进入 edit/update，不重复 create。
- AutoCount 保存成功但 ERP 更新映射失败时，下次重试应能用外部 reference 找回或人工指定 `DocNo`。
- 对金额单据，建议保存后立刻重新读取 AutoCount totals，以 AutoCount 为会计结果来源。

## 常见错误

```text
Login failed
```

检查 AutoCount user/password，不是 SQL password。

```text
Could not load file or assembly ...
```

确保 exe 跟 AutoCount DLL 在同一目录，或设置 assembly probing / copy local，并带上 AutoCount 的 app.config binding redirect。

```text
Account cannot be empty
```

AR Invoice detail 的 `AccNo` 没有给，或 item group 默认 sales account 没维护。

```text
Quotation cannot transfer
```

检查 quotation 是否 approved，以及 `Transferable` 是否为 true。

```text
Item UOM cannot change
```

该 item 已有交易，UOM rate / base UOM 可能不能直接修改。

## 官方参考

- AutoCount Integration Methods: https://wiki.autocountsoft.com/wiki/Integration_Methods
- AutoCount Accounting 2.1 API: https://wiki.autocountsoft.com/wiki/AutoCount_Accounting_2.1_API
- AR Invoice v2: https://wiki.autocountsoft.com/wiki/AR_Invoice_v2
- Programmer Sales Invoice v2: https://wiki.autocountsoft.com/wiki/Programmer%3ASales_Invoice_v2
- Stock Item Maintenance: https://wiki.autocountsoft.com/wiki/Stock_Item_Maintenance
