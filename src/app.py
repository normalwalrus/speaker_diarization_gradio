import gradio as gr
from utils.testing import TesterModule
import text.messages as messages

vad_choices = ['silero-vad']
embedder_choice = ['ECAPA_TDNN_pretrained', 'Wav2Vec2']
clustering_chocie = ['KMeans', 'Spectral']

EXAMPLES = [['audio/british_ministers.wav', 1, 'silero-vad', 'ECAPA_TDNN_pretrained', 'KMeans', False]]


inputs = [gr.Audio(source='upload', type='filepath', label = 'Audio'),
          gr.Slider(0.5, 2, label= 'Window Length (Sec)'),
          gr.Radio(vad_choices, label= 'VAD choice'), gr.Radio(embedder_choice, label='Embedder Choice'), 
          gr.Radio(clustering_chocie, label='Clustering Choice'), gr.Checkbox(label = 'Transcription')]

outputs = ['text']

if __name__ == "__main__":

    Tester = TesterModule()

    app = gr.Interface(
        Tester.predict,
        inputs=inputs,
        outputs=outputs,
        title=messages.TITLE,
        description=messages.NULL,
        examples= EXAMPLES
    ).launch(server_name="0.0.0.0")
    