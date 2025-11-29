使用养成计算器API同步原神背包的物品信息

# 安装&配置

下载此仓库后，修改`config`文件内的示例文件，在其中填写你的米游社Cookie，并另存为`yaml`后缀。

或者，你可以直接通过创建符号链接或者docker共享等方式，直接使用[MihoyoBBSTools](https://github.com/Womsxd/MihoyoBBSTools)的`config`文件夹

# 使用

**API 调用：**

- GOOD格式

  `http://127.0.0.1:20928/inventory/good/<uid>`

  以curl为例：`curl 'http://127.0.0.1:20928/inventory/good/123456789' -H 'accept: application/json'`

## 已知局限

受养成计算器API的限制：

- 获取的物品数量与游戏实时数据相比，有大约10分钟的延迟
- 经验书和精锻用矿只能获取到品质最高的那个的数量
- 当背包中的某种物品的数量多于常规养成所需时，获取的物品数量会少于实际数量。例如，如果你有17亿摩拉时
