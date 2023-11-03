# realtime-asoid
demo to test run realtime arduino trigger for asoid classifier


### Examine a particular video in post-hoc
```commandline
conda activate DLC-GPU
ipython
```

```python
import deeplabcutcore as deeplabcut
import tensorflow as tf
config_path = r'D:\bottomup_clear-hsu-2021-09-21\config.yaml'
video_path = [r'C:\Users\jimi\Documents\GitHub\realtime-asoid\videos\video_1.mp4']
deeplabcut.analyze_videos(config_path, videos=video_path, save_as_csv=True)
```

output csv file can be found in 

C:\Users\jimi\Documents\GitHub\realtime-asoid\videos




