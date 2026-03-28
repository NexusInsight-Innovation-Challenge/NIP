"use client";

import { signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

export function LogoutButton() {
  return (
    <Button 
      variant="destructive" 
      size="sm" 
      onClick={() => signOut({ callbackUrl: "http://localhost:3000/logout" })}
    >
      <LogOut className="size-4 mr-2" /> 
      Logout
    </Button>
  );
}