# cue-splitter
A python script aims to split massive cue+flac tracks


The script assumes the finished tracks in format ``` (@track) [@performer] @title.@ext' ```, and an attempt to split is made for each folder with audio files not in the format.

You can press ctrl+c to pause the splitting process and the script will automatically continue from where breaks next time.

You need to have [split2flac](https://github.com/yuygfgg/split2flac/) and its dependencies installed to run the script.

My modified version of split2flac is recommended because it supports album artist and unicode characters.



<img width="1081" alt="截屏2024-06-05 08 30 23" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/577ca4f1-4872-4428-b42b-488333000633">
