# youtube_download

Download viedo from youtube and use ffmprg to change viedo to mp3 format.  
This project use [pyahocorasick](https://pyahocorasick.readthedocs.io/en/latest/) to compare keyword and try to guess the vocal ant title of the viedo.

## set up

first, you should fill in parameter for path
```python
# SETTINGS
download_path = "" # viedo download path
ffmpeg_path = '' # ffmpeg bin path
project_path = '' # the path of model below
model_name = 'ac.dat'
artist_name = 'artist.yaml'
```

## Using
Run the code. Copy the URL of viedo and paste it for input.  
You can use the following argument to rename or add the kwyword for matching

```
-rn "new file name"
```
rename the the last download file

```
-add -v "keyword:name"
```
add keyword **-v** specify the category is **vocal**.  
other category are **-c** and **-m**, which mean **composer** and **manipulator**

you can also edit the yaml file to maintain keywords. Just call reload to load the yaml file. The command is:
```
-rl
```