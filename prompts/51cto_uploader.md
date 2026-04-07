# Instruction

你现在是一个有着资深编程经历的工程师.
```目前需要编写一个自动化脚本,用于将一个或多个本地的markdown格式文件内容作为博客内容并发布到51CTO博客网站上. 该脚本主要用于处理大批量将本地文章发布到51CTO博客网站的需求.```

---

## Input
1. 用户可指定一个本地markdown格式文件的全路径.
2. 用户可指定一个装有多个本地markdown格式文件的目录的全路径.
3. 以上两种输入为2选1.

---

## Output
1. 脚本需要总结并汇报本次发布的结果信息.其中包括:
    - 上传成功的文章名称和数量
    - 上传失败的的文章名称和数量
    - 返回51CTO博客的用户中心URL: ```https://blog.51cto.com/creative-center/manager```

---

## 实现细节要求

1. 脚本使用python语言进行实现.脚本相关文件存放在当前项目下的51cto_uploader目录中.

2. 脚本应通过附加命令参数的形式接收用户传入的相关参数.

3. 发布文章时如果出现异常,则应记录应将错误记录到日志中.之后程序应向外抛出异常并立刻终止运行.

4. 功能中涉及到操作本地浏览器的功能统一使用selenium库来进行实现.同时, 浏览器则使用本地安装的chrome.selenium操作chrome时所需使用的driver存放在51cto_uploader/drivers/chrome-mac-x64目录中.

---

## 操作步骤

### 步骤1
通过命令行向用户输出操作提示内容.提示内容如下:```请事先在浏览器中完成51CTO博客的用户登陆操作.```

### 步骤2
检查用户是否已经先行登陆51CTO博客.此时可通过调用本地浏览器直接访问51CTO博客的用户中心URL: ```https://blog.51cto.com/creative-center/manager```,并检查页面中的元素是否符合已登陆条件的方式来核查用户是否已经执行了登陆操作.如果发现用户未登陆, 则应向用户发出提示并按照“实现细节要求”中处理异常状态的要求来处理程序运行状态.

### 步骤3
读取一个本地markdown格式文件内容.```如果用户需要发布多个markdown文件时, 要按需加载文件内容,不允许一口气加载所有文章内容到缓存中.```同时,还需要获取并保存当前文件的名称.

### 步骤4
1. 调用本地浏览器打开51CTO博客的发布文章页面: ```https://blog.51cto.com/blogger/publish```.
2. 将当前文件的名称作为文章标题填入到发布文章页面的文章标题输入框内.这里可以通过定位页面中的带有name="title"属性的input标签来找到相应的输入框.
3. 将加载的文章内容填入发布文章页面的文本输入框内.这里可通过定位页面中带有placeholder="请输入正文"属性的textarea标签来找到相应的输入框.
4. 点击发布文章页面中的“发布文章”按钮来将文章发布到51CTO博客中.这里可通过定位页面中带有class=" edit-submit"属性的button标签来找到相应的按钮.
5. 找到页面元素<div class="types-select-box"></div>中的所包含的<span>代码人生</span>页面元素,并对其触发触发click操作操作
6. 点击页面元素<button class="release" id="submitForm">发布</button>来触发文章发布操作.

### 步骤5
通过检查后执行完所有步骤4中所有操作后返回的页面内容来判断是否已经发布成功.通常,51CTO博客在发布完文章后会先对文章内容进行审核操作;因此```如果页面上出现了文章正在审核的相关提示, 可认为是发布成功的状态.```.```若没有检查到发布成功的相关页面元素时,则一律认为是发布失败.```如果发布失败, 则根据页面中的信息总结失败原因并记录.之后,如果还有未发布的文章, 则重复步骤3至步骤5的所有操作.

### 步骤6
根据记录的失败信息来推算出发布成功的相关信息毕竟总结.

### 步骤7
将本次的发布操作总结返回给用户.

---

## 用于判断页面状态的页面元素

### 登陆状态
 检查页面：https://blog.51cto.com/creative-center/manager

|  状态   | 页面元素 |
|  ----  | ----  |
|  已登录  | /html/body/div[2]/div[1]/div/div[1]/div[1]/a |
| 未登录 | 页面跳转到登录页URL: https://home.51cto.com/index?from_service=blog. ```注意: 有可能会跳转到以这个URL为开头的一个URL, 要针对这种情况做处理```.|

### 发布文章状态

发布页面：https://blog.51cto.com/blogger/publish

|  元素   | 实际选择器 |
|  ----  | ----  |
|  标题输入框   |  //*[@id="title"] |
| 正文输入框 | //*[@id="markdownBody"]/div[2]/div[1]/div/div/textarea |
| 发布文章| /html/body/div[1]/div[1]/ul/li[2]/button |
| 文章分类 | //*[@id="oneLever"]/div[22] |
| 发布 | //*[@id="submitForm"] |

### 发布结果状态

|  状态   | 页面元素 |
|  ----  | ----  |
|  发布成功（审核中） | //*[@id="__layout"]/div/div[2]/div/div[1]/span |

---

## 项目结构
- 脚本名称: 51cto_uploader.py
- 目录名称: 51cto_uploader(在工程目录下)
- 日志目录: logs/ (项目根目录下)
- 日志文件: logs/51cto_uploader.log

---

## 依赖
- python版本: 3.14

---

## 编程风格

### 方法注释
每一个function都需要添加方法注释,需要简述当前方法的功能、所有形参的含义、异常抛出的细节以及返回结果的细节.示例如下: 
```python
def acquire_scaling_lock(
    lock_name: str,
    lock_id: str = '',
    expired: int = 600
) -> str:
    """添加伸缩操作锁

    @param lock_name: 锁名
    @type  lock_name: str
    @param lock_id: 锁值, defaults to ''
                    如果未提供锁值,则会自动生成一个锁值
    @type  lock_id: str, optional
    @param expired: 锁的过期时间, defaults to 600
                    以秒为单位, 默认为10分钟/600秒
    @type  expired: int, optional

    @raises: 操作redis失败
    @type:   exception.tool.AcquireScalingLockException
    @raises: 若加锁失败
    @type:   exception.tool.AcquireScalingLockException

    @return: 加锁成功后, 会返回锁值
    @type:   string
    """
```

### 类注释
每一个自定义class都需要添加注释,需要说明当前类的用途以及其可能存在的业务含义.示例如下: 
```python
class Timer():
    """弹性伸缩计时触发器

    若需要修改timer的实现方式(runtime),则只需要修改当前类的类属性TIMER_RUNTIME_CLASS即可;
    即将自定义实现的runtime类通过该类属性依赖注入到timer中;
    其中,自定义runtime必须继承models.timer.runtime.BaseTimerRuntime类进行实现.
    默认的timer是基于tencent cloud的scf来实现的.
    """
```

### 日志格式
参考:
```python
FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s"
```
打印除DEBUG级别外的所有日子.日志文件使用```logging.handlers.TimedRotatingFileHandler```以天为单位进行切割.