import React, { useState, useRef } from 'react';
import { Mic, Square, Loader2, Volume2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface AudioRecorderProps {
    onTranscription: (text: string) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ onTranscription }) => {
    const { t } = useTranslation();
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorder = useRef<MediaRecorder | null>(null);
    const audioChunks = useRef<Blob[]>([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder.current = new MediaRecorder(stream);
            audioChunks.current = [];

            mediaRecorder.current.ondataavailable = (event) => {
                audioChunks.current.push(event.data);
            };

            mediaRecorder.current.onstop = async () => {
                const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
                await handleTranscription(audioBlob);
            };

            mediaRecorder.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Error accessing microphone:", err);
        }
    };

    const stopRecording = () => {
        if (mediaRecorder.current && isRecording) {
            mediaRecorder.current.stop();
            setIsRecording(false);
            mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
        }
    };

    const handleTranscription = async (blob: Blob) => {
        setIsProcessing(true);
        // In a real app, you'd upload this blob. 
        // Here we simulate the process with the backend path.
        console.log("Mocking audio upload and transcription...");
        await new Promise(res => setTimeout(res, 2000));

        // Simulate a successful transcription response
        const mockText = "The handpump near the primary school is leaking and the water is contaminated.";
        onTranscription(mockText);
        setIsProcessing(false);
    };

    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center gap-4">
                {!isRecording ? (
                    <button
                        type="button"
                        onClick={startRecording}
                        className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition"
                    >
                        <Mic size={20} />
                        <span>{t('submit.record_audio')}</span>
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={stopRecording}
                        className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg animate-pulse"
                    >
                        <Square size={20} />
                        <span>Stop Recording...</span>
                    </button>
                )}

                {isProcessing && (
                    <div className="flex items-center gap-2 text-gray-500 text-sm italic">
                        <Loader2 size={16} className="animate-spin" />
                        <span>AI is transcribing...</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AudioRecorder;
