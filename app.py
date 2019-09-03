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
from scipy import interpolate
from PIL import Image
import base64
import io
import re

# import multiprocessing
# pool = multiprocessing.Pool()


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


# default_edf = "E:\\Dropbox (MIT)\\inSight\\Experiment\\Recordings\\combo\\07-20-23-42-56\\mmv@mit.edu\\20190801182425_mmvmitedu_recording.edf"
default_edf = "E:\\Dropbox (MIT)\\inSight\\Experiment\\Recordings\\music\\ladygaga\\mmv@mit.edu\\20190831005053_mmvmitedu_recording.edf"
default_video = "E:\\Dropbox (MIT)\\inSight\\Experiment\\Recordings\\music\\ladygaga\\isthatalright.mp4"
default_fr = 29.97

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

frame_buffer = []


@app.route('/')
def index():
    return render_template('index.html',fr=FR, start_sample=START_SAMPLE,sps=SPS )

@socketio.on('connect')
def connect():
    emit('server', {'message': 'Connected'})

@socketio.on('frame')
def capture(img):
    #convert byte to string
    image_data = re.sub('^data:image/.+;base64,', '', img)
    im = np.array(Image.open(io.BytesIO(base64.b64decode(image_data))))
    # frame = np.array(Image.open(io.BytesIO(base64.b64decode(img))))
    frame_buffer.append(im)
    # print(frame)

@socketio.on('download')
def  download(fr):
    clip = e.ImageSequenceClip(frame_buffer,fps=fr)
    clip.write_videofile('out.mp4',fps=fr)

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

        equipment = f.getEquipment()
        print(f'equipment: {equipment}')
        
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
        # print("Precomputing Splines ... ")
        # mono_points = 500
        # print(EDF.shape)
        # monosplines = np.zeros((EDF.shape[0],mono_points))
        # def spliner(l,d=11,amp=1.5,dir=1,offset=0,res=500):
        #     channels = len(l)
        #     X=np.zeros(channels)
        #     Y=np.zeros(channels)
        #     for i,p in enumerate(l):
        #         theta = (i/channels)*2*np.pi
        #         r = 0.5+(d+amp*p)
        #         X[i] = offset+dir*r*np.cos(theta)
        #         Y[i] = r*np.sin(theta)
        #     X = np.r_[X, X[0]]
        #     Y = np.r_[Y, Y[0]]
        #     tck, u = interpolate.splprep([X, Y], s=0, per=True)
        #     X, Y = interpolate.splev(np.linspace(0, 1, res), tck)
        #     Z=np.zeros(res)
        #     return np.stack([X,Y,Z],axis=1)
        # monosplines = np.array([spliner(sample) for sample in EDF[:,MONO]])
        # dualRsplines  = [spliner(sample,d=5.5,offset=10) for sample in EDF[:,DUAL[:len(DUAL)//2]]]
        # dualLsplines  = [spliner(sample,d=5.5,offset=-10, dir=-1) for sample in EDF[:,DUAL[len(DUAL)//2:]]]

        # print(f"the shape of the splines: {monosplines.shape}")

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