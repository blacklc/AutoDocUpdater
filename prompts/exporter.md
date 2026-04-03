# Instruction

你现在是一个有着资深编程经历的工程师.
```目前需要编写一个自动化脚本,用于将MAC OS 备忘录软件中的相关文章导出为本地文件```.

---

## Input
1. 用户指定的一篇或多篇MAC OS 备忘录中的文章名称.多个文章名称使用逗号分隔.
2. 支持用户指定文章tag.使用-t <tag>的形式进行设定.
3. 导出文件的格式.应该支持PDF以及Markdown格式.默认为Markdown格式
4. 导出文件的存放位置.默认为导出到自动化脚本所在目录中的temp目录中.

---

## Output

1. 对应用户所指定的一篇或多篇文章的本地导出文件. 文件类型应为“.pdf”或“.md”类型.
2. 返回本次导出结果的相关统计数据.数据使用json形式返回.示例如下:
    ```json
        {
            "input": {
                "doc_nums": 2,
                "docs": ["doc1", "doc2"],
                "dir": "/lc/doc_dir"
            },
            "export": {
                "doc_nums": 1,
                "docs": ["doc1"]
            },
            "failed": {
                "doc_nums": 1,
                "err_info": [
                    {"doc2": "未找到文章"}
                ]
            }
        }
    ```

---

## 实现细节要求

1. 脚本使用python语言进行实现.

2. 脚本应通过附加命令参数的形式接收用户传入的相关参数.

3. 在执行操作前需要检查用户输入参数.文章名称参数与文章tag参数必须至少输入一个.若两者都未输入,则表示没有输入必填参数;此时脚本程序应向外抛出异常, 提示用户并立刻终止脚本.若两者都输入,则应该导出对应tag内查询指定名称的文章.

4. 脚本应能够在命令行中随时通报当前的导出进度.进度的展现方式可由你自行掌控.

5. 每一篇文章导出时如果出现异常,则应记录并在脚本执行结果中按照```Output```章节中所规定的返回格式及进行输出.

6. 脚本需要将执行过程输出到指定日志中.每一条日志使用json格式记录.

7. 实现从备忘录app导出文章时，应该```使用备忘录app自带的导出为markdown或pdf格式```的功能；而并非使用第三方库来实现该功能。```注意: 不要调用打印功能```.

8. 通过 UI 自动化来实现操作备忘录app.

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

---

## 项目结构
- 脚本名称: doc_exporter.py
- 目录名称: doc_exporter(在工程目录下)
- 日志目录: logs/ (项目根目录下)
- 日志文件: logs/doc_exporter.log

---

## 依赖
- python版本: 3.14