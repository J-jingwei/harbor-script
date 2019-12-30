# harbor-script
用于存放harbor仓库存储回收脚本


### 需要修改部分：
#### 1、url（可通过进入harbor首页左下角api控制中心查看）；
#### 2、带管理权限的harbor用户名密码；
#### 3、需要排除的项目组project（无需排除设为空列表即可）。

#### 编写该脚本的初衷：
harbor仓库满了，网上找了一圈没找到一个好用的脚本，干脆自己尝试写一个，目前可实现排除特定项目后其余项目组保留每个仓库的几个最近版本，多余版本则删除，回收空间。

##### 如harbor版本不为1.9.0，api本人并未对比api是否一致，可以自行尝试，如api不同自行更改即可。
需要注意得一点是，我们image 版本的tag形式为 x.x.x.20191115152501 (版本+时间)，如镜像版本标记不同需要自行修改一下list_tag 中spilit 切分部分。

---
- ###### *更新日志： 增加traceback便于脚本出错的问题定位，增加requests的Session保持，直接记录auth无需每次提供auth参数，取消requests的Keep_alive，设置最大连接数以及重试次数。*
---
- #### 问题记录：

*2019.12.30 清理脚本挂在服务器上每晚定时执行清理，但最近发现harbor的容量显著增长了，按理说有清理脚本不至于增长那么迅速，在垃圾回收日志中发现有近一个星期并未执行成功该脚本了，然后逐一排查问题；*

##### 第一个问题；
######  问题描述：*发现过滤同一仓库下多个tag时出现报错，发现Harbor仓库中多一个项目，主要原因是tag的命名没有遵循(版本+时间)，导致无法split进行时间比对，导致失败。*
###### 解决办法：*原来是小伙伴做jenkins的镜像新建了一个测试项目，目前也不需要了所以了解后直接果断给该项目删除了，当然我们也可以不删除，在排除列表中加入该项目名，排除即可。*
---
##### 第二个问题；
```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='images.xxx.net', port=443): Max retries exceeded with url: /api/repositories/dev-golang/xxx-yyy-zzz-server/tags (Caused by NewConnectionError('<urllib3.connection.VerifiedHTTPSConnection object at 0x7f1a5e214780>: 
Failed to establish a new connection: [Errno -2] Name or service not known',))
```
######  问题描述：*解决了第一个问题后，又出现一个问题，初步怀疑由于Harbor较长时间未清理，需过滤的操作过多，出现该问题，通过搜索发现requests使用了urllib3库，默认的http connection是keep-alive的，请求过多的保持占用，后续请求无法请求成功*
###### 解决办法：*将requests中Keep_alive设置False关闭，由于这正好需要引入Seesion，正好一起将此脚本开始就应该解决的问题Session，auth之类一块解决，于是对代码进行了修改。*
