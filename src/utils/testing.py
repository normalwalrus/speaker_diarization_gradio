import torch
import os
import pickle
from utils.clustering import ClusterModule
from utils.embedding import EmbedderModule
from utils.vad import VADModule
from utils.audioDataloader import audio_dataloader
from utils.audioSplitter import SplitterModule
from utils.transcription import TransciptionModule
from utils.scoring import ScoringModule
from logzero import logger
from constants import CALLHOME

class TesterModule():
    """
    Class is used to bring all other modules together to allow for diarization testing
    """
    def __init__(self) -> None:
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def main(self, audio, n_clusters, window_length, vad, embedder, clusterer, transcription, assessment, dataset_choice):
        """
        Get the speaker embeddings from the ECAPA_TDNN

        Parameters
        ----------
            wavs: Torch.tensor
                Tensors (function built to receive tensors from audio wave) through the ECAPA-TDNN module to get embeddings
            wav_lens: Integar
                Can just be left as None, specify if you know the length of wavs
            normalize: Boolean
                Get the normalised version of the embedings from ECAPA-TDNN
            device: string
                Specify the device 'cpu' or 'gpu' for computation
        Returns
        ----------
            embeddings : Torch.tensor
                Torch.tensor with the embeddings from ECAPA_TDNN
        """

        VAD = VADModule(vad)
        Embedder = EmbedderModule(embedder)

        match assessment:

            case 'None':

                return self.predict( audio, n_clusters, window_length, VAD, Embedder, clusterer, transcription, assessment)
            
            case _:

                audio_list = CALLHOME.CALLHOME_audio

                path_to_folder = self.dataset_decision(dataset_choice)
                if not path_to_folder:
                    return 'Please select a dataset'
                error_list = []

                for x in audio_list:
                    path = path_to_folder + x +'.wav'
                    error_value = self.predict(path, 0, window_length, VAD, Embedder, clusterer, False, assessment)
                    if error_value != None:
                        error_list.append(error_value)
                average = sum(error_list)/len(error_list)
                return str(average)

    def predict(self, audio, n_clusters, window_length, VAD, Embedder, clusterer, transcription, assessment):

        window_size = int(window_length * 16000)

        #Get tensors from the audio path
        logger.info('Extracting Features in Tensor form...')
        DL = audio_dataloader(path = audio, normalize=True)
        DL.rechannel_resample(0, 16000)
        tensors = DL.y[0][0]

        #Voice Activation Detection (Modularise VAD class soon)
        logger.info('Performing Voice Activity Detction...')
        vad_check, sampling_rate, _ = VAD.silero_vad_inference(tensors ,window_size_samples= window_size)

        if assessment == 'VAD':
            #Setting up VAD check, no need for embeddings or clustering
            labels = None
            index_list = self.vad_check_to_index_list(vad_check)
        
        else:
            #Split the tensors into desired window_size
            logger.info(f'Splitting audio into {window_size/sampling_rate} intervals...')
            Splitter = SplitterModule()
            split_tensors = Splitter.split_audio_tensor(audio, window_size/sampling_rate)

            #Get embeddings
            logger.info(f'Getting embeddings from {Embedder.name}...')
            embedding_list, index_list = self.get_embeddings_with_vad_check(split_tensors, vad_check, Embedder)

            #Cluster the embeddings 
            logger.info(f'Clusering using {clusterer}...')
            Clusterer = ClusterModule(embedding_list, clusterer, n_clusters)
            labels = Clusterer.get_labels()
        
        combine_list = self.get_list_with_index_and_labels(index_list, labels, assessment)

        #Create the final string for presentation
        logger.info(f'Forming final list for display...')
        final_string, final_list, for_assessing = self.get_final_string_without_transcription(combine_list, window_size/sampling_rate)

        #Assessing error rate of the resultant list of tuples
        logger.info(f'Scoring {assessment}...')
        scorer = ScoringModule()
        if scorer.get_ground_truth_path(audio):
            #Testing
            self.export_textfile(scorer.get_ground_truth(scorer.get_ground_truth_path(audio)), 'testing')

            error_rate = scorer.score(audio, for_assessing, assessment)
            final_string = scorer.stringify(error_rate) + final_string

        #If this is testing, return error_rate
        if assessment != 'None':
            return error_rate

        if not (transcription):
            logger.info(f'Display final string without transciption...')
            return final_string

        #Adding Transcriptions
        logger.info(f'Transcripting audio...')
        Transcriber = TransciptionModule()
        transcribed_list = Transcriber.diarization_transcription(final_list, split_tensors, [window_size, sampling_rate])

        #Form final list
        logger.info(f'Display final string with transciption...')
        transcribed_string = self.get_final_string_with_transcription(transcribed_list, final_list)

        logger.info('Exiting out of predict...')
        return transcribed_string
    
    def export_textfile(self, list_temp, name, path = '/../data/text/'):
        with open(os.getcwd()+f'/data/text/{name}.txt', 'w') as f:
            for line in list_temp:
                f.write(f"{line}\n")
    
    def get_final_string_with_transcription(self, transcibed_list, final_list):

        final_string = ''
        for x in range(len(final_list)):
            final_list[x].append(transcibed_list[x])

        for x in range(len(final_list)):
            
            temp = f'Speaker {final_list[x][0]} : {final_list[x][1]}s - {final_list[x][2]}s \n {final_list[x][3]} \n\n'
            final_string+=temp

        return final_string
    
    def get_embeddings_with_vad_check(self, tensors, vad_check, embedder):

        features_list = []
        index_list = []

        for x in range(len(tensors)-1):
            if vad_check[x]:
                features = embedder.get_embeddings(tensors[x])
                features = features.cpu().detach()
                features = features.tolist()
                features_list.append(features[0][0])
                index_list.append(x)
        
        return features_list, index_list
    
    def get_list_with_index_and_labels(self, index_list, labels, assessment):
        combine_list = []
        
        if assessment == 'VAD':
            for x in range(len(index_list)):
                combine_list.append([index_list[x], 'A'])

        else:
            for x in range(len(index_list)):
                combine_list.append([index_list[x], self.speaker_decision(labels[x])])

        
        return combine_list
    
    def dataset_decision(self, label):
        match label:
            case 'None':
                return None
            case 'CALLHOME':
                return os.getcwd() + '/data/audio/CALLHOME/'
            case 'Noised_CALLHOME':
                return os.getcwd() + '/data/audio/noised_CALLHOME/'
            case 'Chatter_CALLHOME':
                return os.getcwd() + '/data/audio/chatter_CALLHOME/'
            
        return None
    
    def speaker_decision(self, label):
        match label:
            case 0:
                return "A"
            case 1:
                return "B"
            case 2:
                return "C"
            case 3:
                return "D"
            case 4:
                return "E"
    
    def get_final_string_without_transcription(self, combine_list, length_of_interval):
        starting = 1
        final_string = ''
        final_list = []
        for_assessing = []

        for x in range(len(combine_list)):
            if starting:
                start = combine_list[x][0] * length_of_interval
                final_string += f'Speaker {combine_list[x][1]} : {round(start,2)}'
                starting = 0
            
            if x != len(combine_list)-1:
                if combine_list[x+1][1] != combine_list[x][1] or combine_list[x+1][0] != combine_list[x][0]+1:
                    end = (combine_list[x][0] + 1) * length_of_interval
                    final_string += f' - {round(end,2)} \n'
                    starting = 1
                    final_list.append([combine_list[x][1], round(start,2), round(end,2)])
                    for_assessing.append((combine_list[x][1], round(start,2), round(end,2)))

            else:
                end = (combine_list[x][0] + 1) * length_of_interval
                final_string += f' - {round(end,2)} \n'
                final_list.append([combine_list[x][1], round(start,2), round(end,2)])
                for_assessing.append((combine_list[x][1], round(start,2), round(end,2)))

        return final_string, final_list, for_assessing
    

    def vad_check_to_index_list(self, vad_check):
        index_list = []
        for x in range(len(vad_check)-1):
            if vad_check[x]:
                index_list.append(x)

        return index_list
