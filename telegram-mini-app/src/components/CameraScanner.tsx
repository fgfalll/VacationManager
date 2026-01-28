import { useState, useRef } from 'react'
import { CameraOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Toast } from 'antd-mobile'
import { useTelegram } from '../hooks/useTelegram'

interface CameraScannerProps {
  onScanComplete: (imageData: string) => void
}

export const CameraScanner: React.FC<CameraScannerProps> = ({ onScanComplete }) => {
  const { webApp, HapticFeedback } = useTelegram()
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [capturing, setCapturing] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const startCamera = async () => {
    try {
      HapticFeedback.impactOccurred('medium')
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      })
      setStream(mediaStream)
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
      }
    } catch (error) {
      Toast.show({
        content: 'Не вдалося отримати доступ до камери',
        icon: 'fail',
      })
    }
  }

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }
  }

  const captureImage = () => {
    HapticFeedback.impactOccurred('heavy')
    setCapturing(true)

    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current
      const canvas = canvasRef.current
      const context = canvas.getContext('2d')

      if (context) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        context.drawImage(video, 0, 0, canvas.width, canvas.height)

        const imageData = canvas.toDataURL('image/jpeg', 0.9)
        onScanComplete(imageData)
        stopCamera()
      }
    }

    setCapturing(false)
  }

  const switchCamera = async () => {
    HapticFeedback.impactOccurred('light')
    stopCamera()
    // Try to get the other camera
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: stream?.getVideoTracks()[0]?.getSettings().facingMode === 'user' ? 'environment' : 'user',
        },
      })
      setStream(mediaStream)
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
      }
    } catch (error) {
      startCamera()
    }
  }

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ position: 'relative', width: '100%', aspectRatio: '3/4', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden' }}>
        {stream ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#fff' }}>
            <CameraOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
            <p>Натисніть кнопку, щоб увімкнути камеру</p>
          </div>
        )}
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>

      <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
        {stream ? (
          <>
            <Button
              block
              color="primary"
              size="large"
              onClick={captureImage}
              disabled={capturing}
            >
              {capturing ? 'Зйомка...' : 'Зняти'}
            </Button>
            <Button
              size="large"
              onClick={switchCamera}
            >
              <ReloadOutlined />
            </Button>
            <Button
              size="large"
              color="danger"
              onClick={stopCamera}
            >
              Скасувати
            </Button>
          </>
        ) : (
          <Button
            block
            color="primary"
            size="large"
            onClick={startCamera}
          >
            <CameraOutlined /> Увімкнути камеру
          </Button>
        )}
      </div>

      <p style={{ marginTop: '16px', fontSize: '12px', color: '#999', textAlign: 'center' }}>
        Порада: Розмістіть документ на рівній поверхні та добре освітліть його перед зйомкою.
      </p>
    </div>
  )
}

export default CameraScanner
