import sys
import os
import django
sys.path.append(r'E:\FinalDesign\Project')
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from core.models import Task

def run():
    tasks = Task.objects.all()
    
    # We will just use some decent placeholder images that fit vertical aspect ratios for waterfall cards
    # Use picsum or unsplash
    images_list = [
        "https://images.unsplash.com/photo-1517849845537-4d257902454a?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
        "https://images.unsplash.com/photo-1543165365-07232ed12fad?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
        "https://images.unsplash.com/photo-1603539947678-ecdca57e3df1?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
        "https://images.unsplash.com/photo-1582213782179-e0d53f98f2ca?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80"
    ]
    
    for task in tasks:
        # Give a 70% chance to have a cover image
        if random.random() < 0.7:
            num_pics = random.randint(1, 3)
            pics = random.sample(images_list, num_pics)
            task.images = pics
            task.save(update_fields=['images'])
    
    print(f"✅ Successfully added images to the tasks!")

if __name__ == "__main__":
    run()
