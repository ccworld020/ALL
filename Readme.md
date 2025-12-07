# 多媒体文件管理系统 (ALL)

一个基于Django的多媒体文件管理系统，支持图片采集、壁纸管理、文件分类和HLS流媒体处理。

## 项目概述

这是一个综合性的多媒体文件管理平台，使用Django 5.2框架开发，包含以下四个核心模块：

- **Konachan**: 从Konachan网站采集和管理系统图片
- **Wallhaven**: 从Wallhaven网站采集和管理壁纸
- **FS**: 文件管理系统，支持文件分类、标签管理和上传
- **HLS**: HLS流媒体文件管理系统

## 技术栈

- **后端**: Django 5.2.8
- **数据库**: SQLite3 (默认)
- **前端**: HTML/CSS/JavaScript
- **HTTP客户端**: requests + cloudscraper (绕过Cloudflare)
- **异步处理**: Daphne ASGI服务器
- **任务队列**: Celery (可选)

## 系统架构

### 目录结构

```
ALL/
├── ALL/                    # 主项目配置
│   ├── settings.py         # Django设置
│   ├── urls.py            # 主URL路由
│   ├── configLoader.py    # 配置加载器
│   └── utils.py           # 工具函数
├── konachan/              # Konachan图片采集模块
├── wallhaven/             # Wallhaven壁纸采集模块
├── fs/                    # 文件管理系统
├── hls/                   # HLS流媒体管理
├── templates/             # HTML模板
├── static/                # 静态文件
├── Media/                 # 媒体文件存储
└── logs/                  # 日志文件
```

## 模块详细说明

### 1. Konachan 模块

**功能**: 从Konachan网站采集和管理图片数据

**核心特性**:
- API数据采集 (支持分页和限制)
- 图片下载管理 (分块下载，支持断点续传)
- 图片预览和画廊展示
- 标签搜索和筛选
- 评级管理 (safe/questionable/explicit)

**数据模型**:
- `KImage`: 存储图片基本信息、URL、尺寸、分辨率等
- 支持MD5去重和下载状态跟踪

**主要视图**:
- `/k/`: Konachan模块首页
- `/k/gallery/`: 图片画廊
- `/k/download/`: 图片下载

### 2. Wallhaven 模块

**功能**: 从Wallhaven网站采集和管理壁纸数据

**核心特性**:
- 壁纸数据采集和分类管理
- 多分辨率壁纸支持
- 纯净度分类 (sfw/sketchy/nsfw)
- 分类标签 (general/anime/people)
- 壁纸下载和预览

**数据模型**:
- `Wallpaper`: 存储壁纸信息、统计数据、颜色信息等
- 支持JSON字段存储缩略图和标签信息

**主要视图**:
- `/w/`: Wallhaven模块首页
- `/w/gallery/`: 壁纸画廊
- `/w/download/`: 壁纸下载

### 3. FS (File System) 模块

**功能**: 通用文件管理系统

**核心特性**:
- 文件上传和管理
- 层级分类系统 (支持父子关系)
- 标签系统
- 文件搜索和筛选
- 缩略图管理
- 文件状态管理 (启用/禁用/删除)

**数据模型**:
- `FileInfo`: 文件基本信息 (MD5、尺寸、类型等)
- `FileAppertain`: 分类和标签 (支持层级结构)
- `FileRelationship`: 文件与分类/标签的多对多关系

**主要视图**:
- `/fs/`: 文件管理首页
- `/fs/upload/`: 文件上传
- `/fs/category/`: 分类管理
- `/fs/tag/`: 标签管理

### 4. HLS 模块

**功能**: HLS流媒体文件管理系统

**核心特性**:
- m3u8文件扫描和解析
- 文件夹级联选择器
- HLS信息管理
- 文件MD5校验
- 媒体信息提取 (分辨率、时长等)

**数据模型**:
- `HLSInfo`: HLS文件信息存储

**主要视图**:
- `/hls/`: HLS管理首页
- `/hls/scan/`: 文件夹扫描
- `/hls/list/`: HLS文件列表

## 安装和部署

### 环境要求

- Python 3.8+
- Django 5.2+
- SQLite3 (默认) 或其他Django支持的数据库

### 安装步骤

1. **克隆项目并安装依赖**
```bash
git clone <repository-url>
cd ALL
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

2. **数据库迁移**
```bash
python manage.py makemigrations fs konachan wallhaven hls
python manage.py migrate
```

3. **创建超级用户 (可选)**
```bash
python manage.py createsuperuser
```

### 运行项目

1. **开发模式**
```bash
python manage.py runserver
```

2. **生产模式 (使用Daphne)**
```bash
daphne ALL.asgi:application -p 8899
```

3. **使用Celery (异步任务)**
```bash
celery -A ALL worker
```

### Docker部署

```bash
# 构建镜像
docker build -t ccfiles:v1.1.* .

# 启动容器
docker-compose -f pv.yaml up -d
```

## 配置说明

### 环境变量

- `DJANGO_SECRET_KEY`: Django密钥
- `DJANGO_DEBUG`: 调试模式 (true/false)
- `DJANGO_ALLOWED_HOSTS`: 允许的主机列表
- `CORS_ALLOW_ALL_ORIGINS`: CORS设置
- `LOG_LEVEL`: 日志级别

### 配置文件

项目使用 `ALL/config.ini` 进行配置，包括：
- 代理设置
- HTTP请求头
- API配置
- 分页设置
- 文件路径配置

## API接口

### Konachan API
- `POST /k/get-data/`: 采集Konachan数据
- `GET /k/gallery/`: 获取图片列表
- `POST /k/download/`: 下载图片

### Wallhaven API
- `POST /w/get-data/`: 采集Wallhaven数据
- `GET /w/gallery/`: 获取壁纸列表
- `POST /w/download/`: 下载壁纸

### FS API
- `POST /fs/upload/`: 上传文件
- `GET /fs/files/`: 获取文件列表
- `POST /fs/category/`: 管理分类

### HLS API
- `GET /hls/folders/`: 获取文件夹列表
- `POST /hls/scan/`: 扫描HLS文件

## 日志系统

项目配置了完整的日志系统：
- 应用日志: `logs/app.log`
- Konachan日志: `logs/KLog.log`
- Wallhaven日志: `logs/wallhaven.log`
- HLS日志: `logs/hls.log`

支持日志轮转和级别控制。

## 安全特性

- CSRF保护
- XSS防护
- SQL注入防护
- 文件上传安全检查
- Cloudflare绕过支持

## 开发说明

### 添加新模块

1. 创建Django应用
2. 在 `settings.py` 中注册应用
3. 在主 `urls.py` 中添加路由
4. 配置数据库模型和迁移

### 扩展API

参考现有模块的API实现，使用统一的错误处理和日志记录。

## 许可证

[请根据实际情况填写许可证信息]

## 贡献

欢迎提交Issue和Pull Request！

## 更新日志

### v1.1.*
- [更新内容]
