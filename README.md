# cue-splitter
A python script splits massive cue+flac tracks. Splitted tracks are saved in the same directory as raw cue&flac and original audio file is removed after double check.

**Tested on 4.4TB mixed files, including 1398 unsplitted flacs**

The script transcode every splitted track to CD quality flac because shnsplit, which hasn't updated for over 15 years, do not support splitting higher quality tracks with one-second accuracy cues, while almost no cue file uses milisecond accuracy.

## The script automatically handles: 

- determining which folder needs processing

- codecs of cue files and convert to utf-8 by default

- ctrl+c pause & resume

- check & remove original track

- tag muiti disc album

~~- separate mixed album in the same folder(e.g. instrument), which is essential for jellyfin mediaserver~~ (need enable manually in script code)

**Warning: don't pause during a split2flac process in wrong folder, it may cause data loss in that folder in some corner cases. If you did, remove the .processing file in that folder before resume.**

## Dependancies

- [split2flac](https://github.com/yuygfgg/split2flac/) and its dependencies

- python3

- chardet

- mutagen

The modified version of split2flac is recommended because it supports album artist and unicode characters.


## Screenshots
<img width="1320" alt="截屏2024-06-07 14 43 59" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/5664f886-4d03-4f56-8810-e336d7d7ead6">
<img width="1334" alt="截屏2024-06-07 14 45 33" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/108e328a-0059-4bb0-ab45-4f49a18e875b">
<img width="1920" alt="截屏2024-06-08 15 37 18" src="https://github.com/yuygfgg/cue-splitter/assets/140488233/c5495aa1-39f7-4196-87d5-c19c5b179f94">
