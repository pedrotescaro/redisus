import { useEffect, useState } from 'react';

import { getInitials } from '../../lib/format';

interface UserAvatarProps {
  name: string;
  src?: string | null;
  imageClassName: string;
  fallbackClassName: string;
}

export function UserAvatar({ name, src, imageClassName, fallbackClassName }: UserAvatarProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const normalizedSrc = src?.trim() || '';

  useEffect(() => {
    setImageFailed(false);
  }, [normalizedSrc]);

  if (normalizedSrc && !imageFailed) {
    return (
      <img
        src={normalizedSrc}
        alt=""
        className={imageClassName}
        referrerPolicy="no-referrer"
        onError={() => setImageFailed(true)}
      />
    );
  }

  return <div className={fallbackClassName}>{getInitials(name)}</div>;
}
