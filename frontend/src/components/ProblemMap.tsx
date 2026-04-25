import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in React Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface ProblemMapProps {
    problems: {
        id: string;
        title: string;
        village_name: string;
        status: string;
        lat?: number | null;
        lng?: number | null;
    }[];
    center?: [number, number];
    zoom?: number;
}

export default function ProblemMap({ problems, center = [20.5937, 78.9629], zoom = 5 }: ProblemMapProps) {
    const renderMarker = (p: ProblemMapProps['problems'][number]) => {
        if (typeof p.lat !== 'number' || typeof p.lng !== 'number' || (p.lat === 0 && p.lng === 0)) {
            return null;
        }

        return (
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
        );
    };

    return (
        <div className="h-full w-full rounded-xl overflow-hidden border border-gray-200 shadow-inner">
            <MapContainer center={center} zoom={zoom} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {problems.map((p) => renderMarker(p))}
            </MapContainer>
        </div>
    );
}
