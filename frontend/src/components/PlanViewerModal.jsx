import { TransformWrapper, TransformComponent, useControls } from 'react-zoom-pan-pinch'
import { X, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'

function Controls({ pageName, onClose }) {
  const { zoomIn, zoomOut, resetTransform } = useControls()
  return (
    <div className="flex items-center justify-between px-4 py-2 bg-black/60 text-white z-10">
      <h2 className="text-sm font-medium truncate">{pageName}</h2>
      <div className="flex items-center gap-2">
        <button onClick={() => zoomIn()} className="p-1.5 hover:bg-white/20 rounded"><ZoomIn size={16} /></button>
        <button onClick={() => zoomOut()} className="p-1.5 hover:bg-white/20 rounded"><ZoomOut size={16} /></button>
        <button onClick={() => resetTransform()} className="p-1.5 hover:bg-white/20 rounded"><RotateCcw size={16} /></button>
        <button onClick={onClose} className="p-1.5 hover:bg-white/20 rounded ml-2"><X size={18} /></button>
      </div>
    </div>
  )
}

export default function PlanViewerModal({ pageName, imageUrl, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex flex-col">
      <TransformWrapper
        initialScale={1}
        minScale={0.1}
        maxScale={8}
        centerOnInit={true}
        doubleClick={{ mode: 'zoomIn', step: 0.7 }}
        wheel={{ step: 0.1 }}
      >
        <Controls pageName={pageName} onClose={onClose} />
        <div className="flex-1 overflow-hidden">
          <TransformComponent
            wrapperStyle={{ width: '100%', height: '100%' }}
            contentStyle={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <img
              src={imageUrl}
              alt={pageName}
              draggable={false}
              className="select-none"
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            />
          </TransformComponent>
        </div>
      </TransformWrapper>
    </div>
  )
}
