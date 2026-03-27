import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function LogoutPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-2xl font-bold">Sesión cerrada correctamente</h1>
        <p className="text-muted-foreground">Has cerrado sesión con éxito.</p>
        <Button asChild>
          <Link href="/">
            Iniciar sesión nuevamente
          </Link>
        </Button>
      </div>
    </div>
  );
}
