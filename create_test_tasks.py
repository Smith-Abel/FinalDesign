import sys
import os
import django
import random
sys.path.append(r'E:\FinalDesign\Project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_helper.settings')
django.setup()

from core.models import Task

def run():
    # 使用本地 media 路径，避免外链 404
    LOCAL_IMAGES = [
        'http://127.0.0.1:8000/media/uploads/demo_1.jpg',
        'http://127.0.0.1:8000/media/uploads/demo_2.jpg',
        'http://127.0.0.1:8000/media/uploads/demo_3.jpg',
        'http://127.0.0.1:8000/media/uploads/demo_4.jpg',
        'http://127.0.0.1:8000/media/uploads/demo_5.jpg',
    ]

    tasks = Task.objects.all()
    for task in tasks:
        # 70% 概率有图，无图则清空之前的外链
        if random.random() < 0.7:
            num = random.randint(1, 2)
            task.images = random.sample(LOCAL_IMAGES, num)
        else:
            task.images = []
        task.save(update_fields=['images'])

    print(f'✅ Updated images for {tasks.count()} tasks with local media URLs')

if __name__ == '__main__':
    run()
