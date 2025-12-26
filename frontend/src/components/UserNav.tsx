import { useEffect, useState } from 'react';

interface User {
  id: string;
  username: string;
  avatar_url: string | null;
}

interface AuthStatus {
  authenticated: boolean;
  user: User | null;
}

export default function UserNav() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/auth/me', {
      credentials: 'include',
    })
      .then((res) => res.json())
      .then((data: AuthStatus) => {
        setAuth(data);
        setLoading(false);
      })
      .catch(() => {
        setAuth({ authenticated: false, user: null });
        setLoading(false);
      });
  }, []);

  const handleLogout = async () => {
    await fetch('http://localhost:8000/api/v1/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
    setAuth({ authenticated: false, user: null });
    window.location.href = '/';
  };

  if (loading) {
    return <span className="text-gray-400">...</span>;
  }

  if (auth?.authenticated && auth.user) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-gray-300">
          {auth.user.username}
        </span>
        <button
          onClick={handleLogout}
          className="text-gray-400 hover:text-amber-400 transition-colors"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <a href="/login" className="hover:text-amber-400 transition-colors">
      Login
    </a>
  );
}
