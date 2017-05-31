# 用微信监控多个服务器的GPU运行情况

## 使用方法：

1. 切换到Python 3环境

2. 安装依赖：

```shell
pip install itchat
pip install requests
```

3. 选择一个服务器作为master服务器，运行

```python
python master.py --address <主服务器IP地址>
```

4. 在多个GPU服务器上运行

```python
python slaver.py --address <主服务器IP地址>
```

## 查询功能

有效指令：
- user：查看用户使用情况
- server：查看服务器列表
- gpu：查看所有GPU使用情况
- gpu <完整IP地址或后缀>：查看指定服务器GPU使用情况

## 警报功能：

检测长时间占用GPU内存但是没有运行的进程，自动发送微信消息给相应用户。

使用该功能需要添加用户的微信账号，修改备注名称，并将服务器账号名与微信备注名成对记录在<`username_to_wechatname.txt`>中，比如：

```shell
xiaoming 小明
lilei 李雷
hanmeimie 韩梅梅
david David
```

警报判定依据为长期满足以下条件：

- 占用GPU内存大于一定阈值（如1000M）
- 进程所在GPU使用率以及进程自身的CPU使用率均低于一定阈值（如10%）
- 距离上次该进程触发警报过去了一段时间（如半小时）

以上数值可根据需要在启动master服务时更改，详见帮助信息：

```python
python master.py -h
```
