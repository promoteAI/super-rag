import logging
import ray
import time
from logging.config import dictConfig
from super_rag.config import settings

# 配置日志
RAY_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[%(asctime)s: %(levelname)s/%(processName)s] %(name)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
            'level': 'INFO',
        }
    },
    'loggers': {
        'LiteLLM': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False,
        },
        'super_rag': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}

def setup_ray_logging():
    dictConfig(RAY_LOGGING_CONFIG)

setup_ray_logging()
logger = logging.getLogger("super_rag.ray_app")

if not ray.is_initialized():
    ray.init(address="auto", ignore_reinit_error=True,local_mode=True)

# 定义Ray Actor用于定时任务/后台任务
def schedule_periodic(remote_func, interval_seconds: float):
    # 用于在后台单独定时调度Ray任务
    @ray.remote
    class PeriodicActor:
        def __init__(self):
            self.running = True

        def run(self):
            while self.running:
                try:
                    remote_func.remote()
                except Exception as e:
                    logger.error(f"Ray periodic task error: {e}", exc_info=True)
                time.sleep(interval_seconds)

        def stop(self):
            self.running = False

    return PeriodicActor.remote()

# worker/actor任务封装
def maybe_schedule_actor(task_name, interval_seconds, ray_task):
    # 实现类似Celery schedule的自动周期执行
    schedule = getattr(settings, "enable_ray_schedule", True)
    if schedule:
        logger.info(f"Scheduling ray task {task_name} every {interval_seconds} seconds.")
        pa = schedule_periodic(ray_task, interval_seconds)
        ray.get(pa.run.remote())

# Ray remote任务定义 (示例：需要你在 config/ray_tasks.py 实现这些函数)
from config import ray_tasks

# 等价于Celery的beat_schedule，自动周期运行
SCHEDULE_CONFIG = [
    ('reconcile-indexes', ray_tasks.reconcile_indexes_task, 3600.0),
]

def main():
    # 周期性调度
    actors = []
    for name, task_func, interval in SCHEDULE_CONFIG:
        actor = schedule_periodic(task_func, interval)
        actors.append(actor)
        # run in background thread – do not call .run.remote() here, but let user manually trigger
    logger.info("All periodic Ray actors started. Ray is now running as a distributed task scheduler.")

    # 启动期间主线程阻塞，可定制成服务模式
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down Ray periodic tasks.")
        for actor in actors:
            ray.get(actor.stop.remote())

if __name__ == "__main__":
    main()
