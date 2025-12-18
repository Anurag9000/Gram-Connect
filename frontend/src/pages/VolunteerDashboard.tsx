import React, { useState } from 'react';
import {
    CheckCircle, Clock, Camera, MapPin,
    ChevronRight, ArrowLeft, Loader2
} from 'lucide-react';

interface VolunteerDashboardProps {
}

export default function VolunteerDashboard() {
    const [selectedTask, setSelectedTask] = useState<any | null>(null);
    const [beforeImage, setBeforeImage] = useState<string | null>(null);
    const [afterImage, setAfterImage] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Mock Tasks
    const tasks = [
        {
            id: 'task-1',
            title: 'Broken Well Pump',
            village: 'Gram Puram',
            location: 'Near Primary School',
            status: 'assigned',
            description: 'The handle of the hand-pump is broken. Needs basic welding or part replacement.',
            assigned_at: '2023-10-25',
        }
    ];

    const handleComplete = async () => {
        if (!afterImage) {
            alert("Please upload an 'After' photo as proof of work.");
            return;
        }
        setIsSubmitting(true);
        // Mock simulation
        await new Promise(res => setTimeout(res, 2000));
        alert("Impact verified! Thank you for your service.");
        setIsSubmitting(false);
        setSelectedTask(null);
    };

    if (selectedTask) {
        return (
            <div className="min-h-screen bg-gray-50 py-12 px-4">
                <div className="max-w-2xl mx-auto">
                    <button
                        onClick={() => setSelectedTask(null)}
                        className="flex items-center gap-2 text-green-700 font-semibold mb-6"
                    >
                        <ArrowLeft size={20} /> Back to My Tasks
                    </button>

                    <div className="bg-white rounded-2xl shadow-lg p-8">
                        <h2 className="text-2xl font-bold text-gray-900 mb-2">{selectedTask.title}</h2>
                        <p className="text-gray-600 mb-6">{selectedTask.description}</p>

                        <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
                            <MapPin size={16} className="text-green-600" />
                            <span>{selectedTask.village}, {selectedTask.location}</span>
                        </div>

                        <div className="space-y-8">
                            <h3 className="text-lg font-bold text-gray-800 border-b pb-2">Verification Proof (Before & After)</h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">Before Photo</p>
                                    <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 bg-gray-50 object-cover overflow-hidden">
                                        {beforeImage ? (
                                            <img src={beforeImage} className="w-full h-full object-cover" />
                                        ) : (
                                            <>
                                                <Camera size={32} className="text-gray-400 mb-2" />
                                                <span className="text-xs text-gray-500">Capture/Upload</span>
                                            </>
                                        )}
                                        <input type="file" className="hidden" accept="image/*" onChange={(e) => setBeforeImage(e.target.files?.[0] ? URL.createObjectURL(e.target.files[0]) : null)} />
                                    </label>
                                </div>

                                <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">After Photo (Required)</p>
                                    <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 bg-gray-50 object-cover overflow-hidden">
                                        {afterImage ? (
                                            <img src={afterImage} className="w-full h-full object-cover" />
                                        ) : (
                                            <>
                                                <Camera size={32} className="text-green-600 mb-2" />
                                                <span className="text-xs text-green-600 font-bold">Verify Completion</span>
                                            </>
                                        )}
                                        <input type="file" className="hidden" accept="image/*" onChange={(e) => setAfterImage(e.target.files?.[0] ? URL.createObjectURL(e.target.files[0]) : null)} />
                                    </label>
                                </div>
                            </div>

                            <button
                                onClick={handleComplete}
                                disabled={isSubmitting || !afterImage}
                                className="w-full bg-green-600 text-white py-4 rounded-xl font-bold text-lg hover:bg-green-700 transition disabled:bg-gray-400 flex items-center justify-center gap-3"
                            >
                                {isSubmitting ? <Loader2 className="animate-spin" /> : <CheckCircle />}
                                {isSubmitting ? 'Verifying Impact...' : 'Submit Resolution Proof'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-4">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h1 className="text-3xl font-extrabold text-gray-900">Volunteer Assignment Dashboard</h1>
                        <p className="text-gray-600">Making a difference, one village at a time.</p>
                    </div>
                    <LanguageToggle />
                </div>

                <div className="grid gap-6">
                    <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                        <Clock className="text-green-600" /> Active Assignments
                    </h2>
                    {tasks.map(task => (
                        <div
                            key={task.id}
                            className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition cursor-pointer flex justify-between items-center group"
                            onClick={() => setSelectedTask(task)}
                        >
                            <div>
                                <h3 className="text-xl font-bold text-gray-900 group-hover:text-green-600 transition mb-1">{task.title}</h3>
                                <div className="flex items-center gap-4 text-sm text-gray-500">
                                    <span className="flex items-center gap-1"><MapPin size={14} /> {task.village}</span>
                                    <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">{task.status}</span>
                                </div>
                            </div>
                            <ChevronRight className="text-gray-300 group-hover:text-green-600 group-hover:translate-x-1 transition" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
