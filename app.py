# Program by Neo Mohsenvand
from flask import Flask,session, render_template, url_for, flash, request, redirect
from wtforms import Form, BooleanField, StringField, PasswordField, validators, SelectField
from flask_socketio import SocketIO, emit
from flask_jsglue import JSGlue


from pylsl import StreamInfo, StreamOutlet
import glob
import random
import time
import os
from shutil import copyfile
from datetime import datetime
import json
import argparse
import pyedflib
import numpy as np
from sklearn.decomposition import FastICA, MiniBatchDictionaryLearning, KernelPCA
import moviepy.editor as e
import gc

class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
            np.int16, np.int32, np.int64, np.uint8,
            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, 
            np.float64)):
            return float(obj)
        elif isinstance(obj,(np.ndarray,)): #### This is the fix
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


default_edf = "E:\\Dropbox (MIT)\\inSight\\Experiment\\Recordings\\combo\\07-20-23-42-56\\mmv@mit.edu\\20190801182425_mmvmitedu_recording.edf"
default_video = "E:\\Dropbox (MIT)\\inSight\\Experiment\\Recordings\\combo\\07-20-23-42-56\\vid_07-20-23-42-56.mp4"
default_fr = 32.0

dual_order = ['T8', 'C4', 'FC6', 'F8', 'Fp2', 'AF4', 'F4', 'Fz', 'FC2', 'Cz', 'CP2', 'Pz', 'Oz', 'O2', 'PO4', 'P4', 'P8', 'CP6',
                'T7', 'C3', 'FC5', 'F7', 'Fp1', 'AF3', 'F3', 'Fz', 'FC1', 'Cz', 'CP1', 'Pz', 'Oz', 'O1', 'PO3', 'P3', 'P7', 'CP5']
natural_order ='T8,C4,FC2,FC6,F4,F8,AF4,Fp2,Fp1,AF3,F7,FC5,F3,Fz,FC1,C3,T7,CP5,P7,P3,CP1,PO3,O1,Oz,O2,P8,PO4,P4,Pz,Cz,CP2,CP6'.split(',')


global EDFPATH
global VIDEOPATH
global FR
global EDF
global START_SAMPLE
global SPS
global W
global DUAL
global MONO

app = Flask(__name__)
# app.secret_key = 'super secret key'
socketio = SocketIO(app)
jsglue = JSGlue(app)


@app.route('/')
def index():
    return render_template('index.html',fr=FR, start_sample=START_SAMPLE)

@socketio.on('connect')
def connect():
    emit('server', {'message': 'Connected'})
    # for j in range(199):
    #     time.sleep(1000)
    #     print('data sent')
    #     # emit('data',json.loads(json.dumps({'edf':EDF[j:j+1000], 
    #     # 'start_sample':START_SAMPLE, 'fr':FR, 'fps':SPS},cls=NumpyEncoder)))
    #     emit('data',{"data":10})

@socketio.on('requestdata')
def send_data(dic):
    emit('server', 'request received.')
    print(dic)
    if dic['dual']:
        data = EDF[dic['begin']:dic['end']:dic['step'],DUAL]
        latent = W[dic['begin']:dic['end']:dic['step']]
        emit('data',json.loads(json.dumps({'dual':True,'edf':data,'latent':latent,'lbl':dual_order},cls=NumpyEncoder)))
    else:
        data = EDF[dic['begin']:dic['end']:dic['step'],MONO]
        latent = W[dic['begin']:dic['end']:dic['step']]
        emit('data',json.loads(json.dumps({'dual':False,'edf':data,'latent':latent,'lbl':natural_order},cls=NumpyEncoder)))
def close_clip(vidya_clip):
    try:
        vidya_clip.reader.close()
        del vidya_clip.reader
        if vidya_clip.audio is not None:
            vidya_clip.audio.reader.close_proc()
            del vidya_clip.audio
        del vidya_clip
    except Exception:
        pass


def preprocess(parser, args):
    edf_path = args.edf
    video_path = args.video
    if not os.path.exists(edf_path):
        parser.error("The file %s does not exist!" % edf_path)
    elif not os.path.exists(video_path):
        parser.error("The file %s does not exist!" % video_path)
    else:
        global EDFPATH
        EDFPATH =os.path.normpath(edf_path)
        global VIDEOPATH
        VIDEOPATH = os.path.normpath(video_path)
        copyfile(VIDEOPATH,os.path.join(os.curdir,'static','v.mp4'))
        global FR
        clip = e.VideoFileClip(VIDEOPATH)
        # print('video frame rate: ', FR)
        FR = clip.fps
        close_clip(clip)

        print(f"file {EDFPATH} is chosen")
        f = pyedflib.EdfReader(EDFPATH)
        
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print('channel names:')
        global MONO
        channel_names = f.getSignalLabels()
        MONO = [channel_names.index(ch) for ch in natural_order]
        print(channel_names)

        global DUAL
        DUAL = [channel_names.index(ch) for ch in dual_order]

        
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        global SPS
        fs = f.getSampleFrequencies()[0]
        SPS = fs
        print(f'Sampling Frequency:{fs}')
        dur = f.getFileDuration()
        sample_count = f.getNSamples()[0]
        print(f"dur: {dur}, samples:{sample_count}, effective fs:{sample_count/dur}")


        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        # n = ceiling (sRate * recordStartTime) + 1
        a = f.read_annotation()
        a = [[np.ceil(fs*(anot[0]/10000000)).astype(np.int)+1,int(anot[2].split(b'#')[1])] for anot in a]
        global START_SAMPLE
        START_SAMPLE = a[0][0]-np.ceil(fs*(a[0][1]/FR)).astype(np.int)
        
        print(f'Annotations:')
        print(f'start: {a[0]}, end: {a[-1]}')
        print(f'video starts at sample {START_SAMPLE}')

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Processing ... ")
        n = f.signals_in_file
        edf = np.zeros((n, f.getNSamples()[0]))
        for i in np.arange(n):
            edf[i, :] = f.readSignal(i)
        edf = edf[:32,:]
        channel_count,num_samples = edf.shape
        print(f"file is processed to an array of shape {edf.shape}")

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Rereferencing and standardizing ...")
        # dc component of the signal
        edf = edf - np.mean(edf, axis=1).reshape(channel_count,1) # all channels shifted to avg=0
        # finding the average reference
        edf = edf - np.mean(edf, axis=0).reshape(1,num_samples) # rereferencing all channels on average
        # standardizing
        edf = edf/(np.std(edf, axis=1).reshape(channel_count,1))
        edf = edf.transpose()
        global EDF
        EDF = edf
        del edf
        gc.collect()

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("dimensionality reduction ... ")
        model = MiniBatchDictionaryLearning(n_components=3, alpha=0.1,
                                                  n_iter=50, batch_size=30,
                                                  random_state=0,
                                                  positive_dict=True)
        # model = FastICA(n_components=3, random_state=0)
        global W
        W = model.fit_transform(EDF)

        W = W-np.mean(W,axis=0).reshape(1,3)
        W = 0.5+ 0.5*W/np.std(W,axis=0).reshape(1,3)
        print(f'min: {np.min(W)}, max: {np.max(W)}, mean: {np.mean(W)}, std: {np.std(W)}')
        print('file processed. Data is ready to be served')

        
        # TODO control the eeg vis using the video playback events, streaming the edf content
        # TODO construct the eeg visualization



        

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--edf', nargs='?', default=default_edf, type=str
         ,help="path to the edf file")
    parser.add_argument('--video', nargs='?', default=default_video, type=str
        ,help="path to the video file")
    # parser.add_argument('--fr', nargs='?', default=default_fr, type=float, help="video frame rate")

    args = parser.parse_args()
    preprocess(parser,args)
    # is_valid_fr(parser, args.fr)

    socketio.run(app, debug=True)