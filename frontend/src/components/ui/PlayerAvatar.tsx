import { useEffect, useState } from 'react'
import { getPlayerImage } from '../../api/playerImages'
import Badge from './Badge'

interface Props {
  name: string
  playerId?: string
  imageUrl?: string | null
  position?: string
  size?: 'small' | 'medium' | 'large' | 'hero'
  className?: string
}

function getInitials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return `${words[0][0] ?? ''}${words.length > 1 ? words[words.length - 1][0] ?? '' : ''}`.toUpperCase()
}

function avatarTone(name: string) {
  const hash = Array.from(name).reduce((total, character) => total + character.charCodeAt(0), 0)
  return hash % 5
}

export default function PlayerAvatar({
  name,
  playerId,
  imageUrl = null,
  position,
  size = 'medium',
  className = '',
}: Props) {
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(imageUrl)
  const [imageFailed, setImageFailed] = useState(false)

  useEffect(() => {
    setResolvedUrl(imageUrl)
    setImageFailed(false)

    if (imageUrl || !playerId) return

    const controller = new AbortController()
    getPlayerImage(playerId, controller.signal)
      .then((response) => setResolvedUrl(response.image_url))
      .catch(() => setResolvedUrl(null))

    return () => controller.abort()
  }, [imageUrl, playerId])

  const showImage = Boolean(resolvedUrl) && !imageFailed

  return (
    <div className={`player-avatar player-avatar--${size} player-avatar--tone-${avatarTone(name)} ${className}`.trim()}>
      {showImage ? (
        <img
          alt={`${name} player portrait`}
          src={resolvedUrl ?? undefined}
          onError={() => setImageFailed(true)}
          referrerPolicy="no-referrer"
        />
      ) : (
        <div className="player-avatar__fallback" role="img" aria-label={`${name} avatar`}>
          <span aria-hidden="true">{getInitials(name)}</span>
        </div>
      )}
      {position ? <Badge className="player-avatar__position" tone="accent">{position}</Badge> : null}
    </div>
  )
}