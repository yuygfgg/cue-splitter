# cue-splitter
A python script splits massive cue+flac tracks. Splitted tracks are saved in the same directory as raw cue&flac and original audio file is removed after double check.


The script transcode every splitted track to CD quality flac because shnsplit, which hasn't updated for over 15 years, do not support splitting higher quality tracks with one-second accuracy cues, while almost no cue file uses milisecond accuracy.

## The script automatically handles: 

- determining which folder needs processing

- codecs of cue files and convert to utf-8 by default

- check & remove original track

- tag muiti-disc albums

## Usage (Docker)
```
alias cue-splitter='docker run -v "$(pwd)":/workdir -e PUID=$(id -u) -e PGID=$(id -g) -it --rm gekowa/cue-splitter'
```
Then, 
```
cd music-dir
cue-splitter
```

## Dependancies

- [split2flac](https://github.com/yuygfgg/split2flac/) and its dependencies (The modified version of split2flac is recommended because it supports album artist and unicode characters.)

- python3

- chardet

- mutagen

## Screenshots
<img width="1320" alt="截屏2024-06-07 14 43 59" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/5664f886-4d03-4f56-8810-e336d7d7ead6">
<img width="1334" alt="截屏2024-06-07 14 45 33" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/108e328a-0059-4bb0-ab45-4f49a18e875b">
<img width="1920" alt="截屏2024-06-08 15 37 18" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/c5495aa1-39f7-4196-87d5-c19c5b179f94">
