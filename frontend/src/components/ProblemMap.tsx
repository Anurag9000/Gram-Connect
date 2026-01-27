import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in React Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface ProblemMapProps {
    problems: any[];
    center?: [number, number];
    zoom?: number;
}

const ProblemMap: React.FC<ProblemMapProps> = ({ problems, center = [20.5937, 78.9629], zoom = 5 }) => {
    return (
        <div className="h-full w-full rounded-xl overflow-hidden border border-gray-200 shadow-inner">
            <MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {problems.map((p) => (
                    (p.lat && p.lng) ? (
                        <Marker key={p.id} position={[p.lat, p.lng]}>
                            <Popup>
                                <div className="p-1">
                                    <h3 className="font-bold text-gray-800">{p.title}</h3>
                                    <p className="text-xs text-gray-600">{p.village_name}</p>
                                    <span className={`text-[10px] font-bold px-1 rounded ${p.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                                        {p.status.toUpperCase()}
                                    </span>
                                </div>
                            </Popup>
                        </Marker>
                    ) : null
                ))}
            </MapContainer>
        </div>
    );
};

export default ProblemMap;
