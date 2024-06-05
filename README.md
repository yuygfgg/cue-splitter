# cue-splitter
A python script aims to split massive cue+flac tracks


The script assumes the finished tracks in format ``` (@track) [@performer] @title.@ext' ```, and an attempt to split is made for each folder with audio files not in the format.

You can press ctrl+c to pause the splitting process and the script will automatically continue from where breaks next time.

You need to have [split2flac](https://github.com/ftrvxmtrx/split2flac/) and its dependencies installed to run the script.

