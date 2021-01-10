import sys
import numpy as np
import os

#image_list = sys.argv[1]
galary = 'ORL_face_dataset_test_galary.txt'
probe = 'ORL_face_dataset_test_probe.txt'

#f_l=open(os.path.join(galary), 'w+')
galary_IDs=np.zeros((50,1))
galary_features=np.zeros((50,512))

i=0
with open(galary, 'r') as f:
    lines= f.readlines()
    f.close()
    for line in lines:
        #filename = line[:-1]
        words=line.split(' ')
        ID=int(words[1])
        words=words[0].split('/')
        feature_save_name='face_feature/'+words[1]+'/'+words[2].split('.')[0]+'.npy'
        #print ID
        #print feature_save_name    
        c = np.load(feature_save_name)
        #print c.shape
        galary_IDs[i,0]=ID
        galary_features[i,:]=c
        i=i+1
        #print c
#print galary_IDs
with open(probe, 'r') as f:
    lines= f.readlines()
    f.close()
    for line in lines:
        #filename = line[:-1]
        words=line.split(' ')
        ID=int(words[1])
        words=words[0].split('/')
        feature_save_name='face_feature/'+words[1]+'/'+words[2].split('.')[0]+'.npy'
        #print ID
        #print feature_save_name    
        probe = np.load(feature_save_name)
        #print probe
        #======= your code =========

        #======= your code =========

