# -*- coding: UTF-8 -*-
'''
Created on 2020年1月19日

@author: danny
'''
#https://stackoverflow.com/questions/27473526/download-only-audio-from-youtube-video-using-youtube-dl-in-python-script
import youtube_dl
import ahocorasick

import shlex
import os
import re
from enum import IntEnum
from ruamel_yaml import YAML, yaml_object
from pathlib import Path
import pickle

# SETTINGS
download_path = ""
ffmpeg_path = ''
project_path = ''
model_name = 'ac.dat'
artist_name = 'artist.yaml'


class parse_string():
    '''
    split and parse title string and guess vocl, title etc...
    '''
    def __init__(self, inStr):
        self.inStr = inStr.lower()
        self.vocal = []
        self.title = []
        self.attr = []
        self.Start()
        self.clean()
    
    
    def clean(self):
        '''clean result'''
        self.vocal = self._clean(self.vocal)
        self.title = self._clean(self.title)
        self.attr = self._clean(self.attr) 
        self.result = {
            'vocal' : self.vocal,
            'title' : self.title,
            'attr' : self.attr,            
        }
        
            
    def GerResult(self):
        '''return parse result'''
        return self.result
        
        
    def Start(self):
        '''start to parse'''
        self.split_paragraph(self.inStr)        
        
        
    def split_paragraph(self, inStr):
        '''split string in multy part'''
        # char of paragraph split string in multy part 
        self.paragraph_char = [
            '/',
            '／',
            '−', # (unicode U+2212) not ascii '-' (U+002D)
            '-', # (U+002D) '-' same as ascii code
        ]

        regexPattern = '|'.join(self._escape_chars(self.paragraph_char))

        # split to paragraph
        parts = list(self.no_empty_spit(regexPattern, inStr))

        # split block
        for part in parts:
            self.split_block(part)
        
        
    def split_block(self, inStr):
        '''
        split out string in side of block and the other
        and then split outside block string by space
        '''
        # string between block char can't be split
        
        self.block_char = {
            '{' : '}',
            '[' : ']',
            '(' : ')',
            '【' : '】',
            '「' : '」',
            '『' : '』',
        }
       
        # initial string parse parameter
        end = 1
        blockhead, start = (inStr[0], 1) if inStr[0] in self.block_char else ('', 0)
        for c in inStr[1:]:
            if self.block_char.get(blockhead, '') == c:
                # commit inside block string
                self.attr.append(inStr[start:end])
                # reset parameter
                blockhead = ''
                start = end + 1
            elif self.block_char.get(c, '') != '' and blockhead == '':
                # commit outside block string
                self.split_feat(inStr[start:end])
                # move mode to inside
                blockhead = c
                start = end + 1
            end += 1
            
        # commitfor last part 
        self.split_feat(inStr[start:end])
        
        
    def split_feat(self, inStr):
        '''parse for feature'''
        feature = [
            'feat.', 
            'ft.',
        ]
        
        for f in feature:
            index = inStr.find(f)
            if index != -1:
                self.vocal.append(inStr[index + len(f):])
                if index > 0:
                    self.title.append(inStr[:index])
                return
        self.title.append(inStr)
            
            
    def _escape_chars(self, inChars):
        '''
        return escape patter of regular expressions
        
        parameter:
            inChars(list): list of char 
        
        return:
            (string): list of escape char
        '''
        return map(re.escape, inChars)
    
    def _clean(self, strs):
        result = []
        for s in strs:
            # get single not space char or string between no space char
            result.extend(re.findall(r'\S.*\S|\S', s))
        return result

    def no_empty_spit(self, pattern, string, maxsplit=0, flags=0):
        '''
        return re.split without empty string
        '''
        return filter(None, re.split(pattern, string, maxsplit, flags))


def del_interval(temp_tuple, InStr):
    '''return no Instr substring in range of temp_tuple'''
    # merage overlap interval
    temp_tuple.sort(key=lambda interval: interval[0])
    merged = [temp_tuple[0]]
    for current in temp_tuple:
        previous = merged[-1]
        if current[0] <= previous[1]:
            previous[1] = max(previous[1], current[1])
        else:
            merged.append(current)
    
    # combine mo repeat interval
    start = 0
    result = ''  
    for interval in merged:
        end = interval[0]
        result += InStr[start:end]
        start = interval[1] + 1
    result += InStr[start:]
    return result

# prepare to dump to yaml
yaml = YAML()

@yaml_object(yaml)
class song_tag(IntEnum):
    '''enum for aong tag'''
    VOCAL = 1
    COMPOSER = 2
    MANIPULATOR = 3 # (調教)https://vocadb.net/T/485/voice-manipulator

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_scalar(
            u'!song_tag',
            '{}-{}'.format(node._name_, node._value_)
        )
    

    @classmethod
    def from_yaml(cls, constructor, node):
        # this will raise error in enum
        return cls(*node.value.split('-'))

# createa dict for enum because of suck yaml not suport loading enum
song_tag_dict = {
    song_tag.VOCAL : 'vocal' ,
    song_tag.COMPOSER : 'composer',
    song_tag.MANIPULATOR : 'manipulator',
}

song_tag_dict_reverse = {
    'vocal' : song_tag.VOCAL,
    'composer' : song_tag.COMPOSER,
    'manipulator' : song_tag.MANIPULATOR,
}

        
class song_data():
    '''parse and guess song info like autho, vocal...'''
    def __init__(self, load = True, *, from_yaml = False, info = None):
        '''
        initial for ac_auto and tag,
        and then start to parse info
        parameters:
            info (dict): info of song
            load (bool): decide to load from file or create a new one ac_auto
            from_yaml (bool): decide to load from taml config. or pickle file
        '''
        if not load:
            # build ac_auto to compare sting
            self.ac = ahocorasick.Automaton()
            self.ac.make_automaton()
        else:
            self.load(from_yaml)  
            
        # try to parse
        if info != None:
            self.new_info(info)



    def clean(self):
        '''clean the song data going to download'''
        self.result = {
            'vocal' : self.tag[song_tag.VOCAL], # combine vocal
            'composer' : list(self.tag[song_tag.COMPOSER]),
            'manipulator' : list(self.tag[song_tag.MANIPULATOR]),
            'title' : self.ps_result['title'],
            'attr' : self.ps_result['attr'],
            'match' : self.match,
        }
        
    
    def guess(self):
        '''guess vocal, composer and manipulator'''
        # guess from title
        self.ac.find_all(self.info['title'].lower(), self._add_result_delete)
                            
        # if title not found vocal, try to find in tag
        if len(self.tag[song_tag.VOCAL]) == 0:
            for tag in self.info['tags']:
                self.ac.find_all(tag.lower(), self._add_result)

        # if composer not found, parse uploader
        if len(self.tag[song_tag.COMPOSER]) == 0:
            self.ac.find_all(self.info['uploader'], self._add_result)

        # if composer not found, use uploader
        if len(self.tag[song_tag.COMPOSER]) == 0:
            self.tag[song_tag.COMPOSER].add(self.info['uploader'])
            
        # delete overlap
        title = del_interval(self._del_str_index, self.info['title']) if len(self._del_str_index) != 0 else self.info['title']
        
        # parse title
        self.ps = parse_string(title)
        self.ps_result = self.ps.GerResult()

        # merage vocal
        self.tag[song_tag.VOCAL] = [' X '.join(self.tag[song_tag.VOCAL])] if len(self.tag[song_tag.VOCAL]) != 0 else []
        self.tag[song_tag.VOCAL].extend(self.ps_result['vocal'])
        if len(self.tag[song_tag.VOCAL]) == 0:
            self.tag[song_tag.VOCAL] = ['']
        
    
    def _add_result_delete(self, end_index, group):    
        self._add_result(end_index, group)
        self._del_str_index.append([end_index - len(group[2]) + 1, end_index])


    def _add_result(self, end_index, group):
        # print([end_index - len(group[2]) + 1, end_index], group[2])
        self.tag[group[0]].add(group[1])
        self.match.append(group[1])
        
    
    def new_info(self, info):
        ''' parse new info'''
        # initial
        self.info = info
        self._del_str_index = [] # for delete string
        self.tag = {
            song_tag.VOCAL : set(),
            song_tag.COMPOSER : set(),
            song_tag.MANIPULATOR : set(),
        }
        self.match = []

        # start to parse
        self.guess()
        self.clean()
        
    
    def save(self, save_yaml = True): 
        '''save acauto and config'''
        path = Path(project_path)
        # dump ac object
        with open(path / model_name, 'wb') as file:
            pickle.dump(self.ac, file)
        # save yaml
        if save_yaml:
            self.save_keyword()
    
    
    def save_keyword(self):
        '''save keyword and map value in yaml format'''
        path = Path(project_path)
        # dump key and value
        artist = {
           'vocal' : {},
           'composer' : {},
           'manipulator' : {},
        }
        keys = self.ac.keys()
        values = self.ac.values()
        for k, v in zip(keys, values):
            artist[song_tag_dict[v[0]]].update({k : v[1]})

        with open(path / artist_name, 'w', encoding = 'utf-8') as file:
            yaml.dump(artist, file)
            
        
    def load(self, artist_file = False):
        '''load ac auto from pickle file or use yaml file to build'''
        path = Path(project_path)
        if not artist_file:
            # load from pickle file
            with open(path / model_name, 'rb') as file:
                self.ac = pickle.load(file)
        else:
            self.ac = ahocorasick.Automaton()
            # load from key word and build new ac_auto
            with open(path / artist_name, 'r', encoding='utf-8') as file:
                data = yaml.load(file)
            # add to ac model
            for category, names in data.items():
                for key, value in names.items():
                    self.add_word(key, (song_tag_dict_reverse[category], value, key), False)
            # ready for search
            self.ac.make_automaton()

            
    def add_word(self, key, value, commit = True):
        '''add key word to the ac_auto'''
        self.ac.add_word(key, value) 
        if commit:
            self.ac.make_automaton()
        
        
class music_downlad():
    def __init__(self, url, load = True, *, from_yaml = False):
        '''
        initial the downloader
        
        paramrter:
            url (str): website url
            load (bool): decide to load from file or create a new one ac_auto
            from_yaml (bool): decide to load from taml config. or pickle file
            **kwargs (sict): other args for downloader opt
        '''
        self.title = u'%(title)s.%(ext)s' # default
        self.song_data = song_data(load, from_yaml = from_yaml)
        # viedo path
        self.new_url(url)
        

    def new_url(self, url):
        self.url = url
        self.info = self.GetInfo(self.url)        
        # parse download info
        self.song_data.new_info(self.info)
        self.data = self.song_data.result
        # print(self.data)
        
        
    def GetInfo(self, url):
        '''return the information of the viedeo'''
        with youtube_dl.YoutubeDL() as ydl:
            return ydl.extract_info(url, download=False)
        

    def download(self, **kwargs):
        '''start to download'''
        # merage download title
        self.title = self.data['vocal'][0] + ' ' + self.data['title'][0]
        # initial parameter
        self.opts_ini(**kwargs)
        try:
            with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([self.url])
        except:
            # request frmat not found
            self.ydl_opts['format'] = 'best'
            with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([self.url])
                            
        
    def opts_ini(self, **kwargs):
        self.ydl_opts = {
            'prefer_ffmpeg': True,
            'ffmpeg_location' : ffmpeg_path,
            'format': 'bestaudio/opus',
            'outtmpl': self.title + '.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
                },
                {'key': 'FFmpegMetadata'},
            ],
            'postprocessor_args': [
                '-ar', '16000',
                #'-metadata', f'Composer="{self.data["composer"]}"',
            ],
            'verbose' : False,
            'progress_hooks': [self._hook],
            'keepvideo' : False,
        }
        self.ydl_opts.update(kwargs)
        
    
    def _hook(self, d):
        '''hook will block the program'''
        if d['status'] == 'finished':
            self.title = d['filename']
            self.title = self.title[:self.title.rfind('.')]
            print(f'下載成功，準備轉檔中...\n')
            
    def _downloading(self):
        pass
    
    
    def _complete(self):
        pass


def add_word(md, specific, inStr):
    '''add word to ac auto'''    
    if specific == '-v':
        category = song_tag.VOCAL
    elif specific == '-c':
        category = song_tag.COMPOSER
    elif specific == '-m':
        category = song_tag.MANIPULATOR

    new_kw = inStr.split(':')
    
    md.song_data.add_word(new_kw[0].lower(), (category, new_kw[1], new_kw[0].lower()))
    
    

def rename(old_name, new_name):
    os.rename(old_name + '.mp3', new_name + '.mp3')
    


def new_download(md, url):
    '''download new viedo''' 
    md.new_url(url)
    md.download()


def command(md, inStr):
    '''parse for command input'''
    cmd = shlex.split(inStr)
    modify = False
    cm = iter(cmd)
    for c in cm:
        if c.find('https://') != -1:
            new_download(md, c)
            return
        elif c == '-rn':
            c = next(cm)
            rename(md.title, c)
            print('更名成功')
        elif c == '-add':
            c = next(cm) # get next value
            if c == '-v' or c == '-c' or c == '-m':
                add_word(md, c, next(cm))
                print("添加成功")
                modify = True
        elif c == '-rl':
            md.song_data.load(True)
            print("載入成功")
            modify = True
                
    if modify:
        md.song_data.save()
        md.song_data.ac.make_automaton()
    
    
def main():
    # download path
    os.chdir(download_path)
    inStr = input('請輸入網址:\n')
    md = music_downlad(inStr, True, from_yaml = False)
    md.download()
    
    while(1):
        inStr = input(
            f'目前的檔名為{md.title}\n' + 
            f'候選檔名為: {md.data["title"]}\t其他屬性有 {md.data["attr"]}\n' + 
            f'候選主唱為{md.data["vocal"]}\t' + 
            f'候選樂師為{md.data["composer"]}\n' + 
            f'匹配到的關鍵詞有{md.data["match"]}\n' + 
            '可輸入參數-rn "新檔名" 來更改檔名(雙引號別忘了)\n' +
            '輸入 -add 後 輸入 -v, -c, 或-m來指定主唱、樂師與調教，接者輸入 "關鍵詞:對象" 來添加數據\n' +
            '輸入 -rl 從yaml檔來重新讀取關鍵詞\n' + 
            '或直接貼上網址下載別的影片\n')
        
        command(md, inStr)
        
    #  -add -v "lily:Lily" -rn "Lily hearts"

if __name__ == '__main__':
    main()