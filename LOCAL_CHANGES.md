# 本地改动说明

本分支为 [krkr521/maibot_identity_plugin](https://github.com/krkr521/maibot_identity_plugin/tree/local/custom) 的本地定制快照。
原项目：[Alcpare/maibot_identity_plugin](https://github.com/Alcpare/maibot_identity_plugin)。
对照基线：`add584e57dfd4ca4f664d93cdef7aa419148b454`；整理日期：2026-11-13。

## 相对基线的主要改动

- 人工身份锁定优先，读取印象卡片的动态关系与好感。
- 向其他插件提供已核实身份及关系的只读接口，关系分数不能授予主人权限。

## 安装与配置

```sh
git clone --branch local/custom https://github.com/krkr521/maibot_identity_plugin.git
```

将仓库放入 MaiBot 插件目录，按原说明安装依赖并在自己的实例中配置。插件 ID 和原作者署名保留，替换同 ID 插件前请备份。
本分支来自定制宿主环境。涉及扩展 RPC、Decision 或后台任务接口的能力需要对应宿主支持；不能据此认定与所有官方 MaiBot 版本兼容。

## 发布范围

保留原许可证及第三方署名。发布内容为源码、通用模板、文档和测试；不包含本机配置、配置备份、Cookie、访问令牌、语音样本、付款码、聊天记录、实际记忆或私有提交历史。
本地部署笔记已改写为通用说明，运行数据由安装者自行管理。
