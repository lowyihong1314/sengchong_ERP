# Sengchong Website Ownership

目标：`sengchong.com` 只负责公开页面渲染。官网内容、服务分类、产品/项目图库、联系资料、首页展示顺序、哪些图片可以公开，都必须交给 ERP 管理。

## Final Rule

- `sengchong.com` 不再有独立 login。
- `sengchong.com` 不再有独立后台。
- `sengchong.com` 不再直接维护产品、服务、联系资料或图片数据。
- `sengchong.com` 只读取 ERP 已发布的数据，然后渲染公开页面。
- 所有后台管理入口只保留在 `erp.sengchong.com`。

这条规则的原因是避免两个后台同时改同一批官网内容。以后业务人员只需要登录 ERP，就能管理 AutoCount 业务数据和官网展示内容。

## Public Site Responsibility

`sengchong.com` 只允许做这些事：

- 渲染首页
- 渲染服务分类
- 渲染公开图库
- 渲染公开项目案例
- 渲染公开联系方式
- 读取 ERP 发布后的只读内容

`sengchong.com` 不允许做这些事：

- 用户登录
- 用户注册
- 后台 CRUD
- 上传图片
- 修改服务分类
- 修改产品图库
- 修改联系方式
- 显示 quotation、invoice、AR payment、supplier cost、customer private data

## ERP Responsibility

ERP 需要负责全部官网内容管理：

- Website settings
  - 公司名
  - WhatsApp / phone
  - email
  - address
  - social links
  - 首页主图 / 排序
- Service categories
  - 电视机橱
  - 商场橱
  - 厨房橱
  - 衣橱
  - 床头柜
  - 拱门
  - 水盆橱
  - 展示柜
  - 设计
- Project gallery
  - 每个 project 可以保存多张图片
  - 图片可以选择 service category
  - 图片可以标记 public/private
  - 图片可以标记 website visible
  - 图片可以设置 sort order
  - 图片可以设置 caption/alt text
- Website publishing
  - 只发布明确允许公开的图片
  - 只发布已完成或手动允许公开的 project
  - 隐藏客户隐私、金额、成本、供应商、AutoCount 单据资料

## Project Photos

Project 需要支持多图保存。建议每张图片最少保存这些字段：

- photo id
- company
- project code
- file path or object storage key
- original filename
- thumbnail path
- service category
- caption
- alt text
- is public
- website visible
- sort order
- uploaded by
- uploaded at

Project detail 应该有一个 Photos tab：

- upload multiple photos
- preview thumbnails
- reorder photos
- mark public/private
- toggle website visible
- choose service category
- set cover image
- delete or archive photo

默认规则：

- 新上传图片默认 private。
- 新上传图片默认不显示在官网。
- 只有用户手动打开 `website visible` 后，官网才可以读取。
- 如果 project 还没完成，也可以手动发布，但必须是明确选择。

## Public Gallery Rules

官网图库只能读取符合条件的图片：

- `is public = true`
- `website visible = true`
- belongs to current company/site
- file exists
- project/customer private fields are not returned

公开 API 返回的数据应该只包含：

- photo url
- thumbnail url
- service category
- caption
- alt text
- project display title if allowed
- sort order

公开 API 不应该返回：

- debtor code/name
- phone
- site address
- quotation doc no
- invoice doc no
- AR payment doc no
- quoted total
- collected total
- outstanding
- estimated cost
- actual cost
- margin
- supplier/AP data

## Suggested ERP Modules

新增或升级这些 ERP 模块：

- `projects`
  - 加 Photos tab
  - 支持 project 多图
  - 支持选择哪些图片允许官网显示
- `project-photos`
  - 图片上传、排序、发布状态、分类管理
- `website-content`
  - 首页、服务分类、联系资料、图库展示顺序
- `website-preview`
  - 在 ERP 里预览公开站会看到的结果

## Migration Rule

旧 `sengchong/` 后台页面要逐步移除：

- `sengchong/templates/login.html` 不再作为后台入口。
- `sengchong/templates/register.html` 不再开放。
- `sengchong/templates/backend.html` 不再维护业务内容。
- 旧图片可以迁移成 ERP `project-photos` 或 `website-content` 记录。
- 迁移后，公开站模板只保留展示逻辑。

## Implementation Order

1. 在 ERP DB 增加 `erp_project_photos` 表。
2. 在 project detail 增加 Photos tab。
3. 支持 project 多图上传和 thumbnail。
4. 增加 `isPublic` 和 `websiteVisible` 两个明确开关。
5. 增加公开只读 API，例如 `/public-api/gallery`。
6. 修改 `sengchong.com` 页面只读取公开 API。
7. 移除旧官网 login/register/backend route 和模板入口。
8. 做 ERP website preview，确认公开内容才发布。

## Security Rule

官网发布必须默认保守：

- private by default
- not website visible by default
- never expose accounting/customer private fields
- ERP admin/sales role 才能发布图片到官网
- 每次发布状态修改以后，未来应写入 audit log

