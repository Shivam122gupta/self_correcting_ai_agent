import React from "react";
import { Button } from "@/components/ui/button";

export interface NavigationSection {
  title: string;
  href: string;
  isActive?: boolean;
}

export interface HeaderProps {
  navigationData: NavigationSection[];
}

export default function Header({ navigationData }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
            ⚡
          </div>
          <span className="text-lg font-extrabold tracking-tight">SelfCorrect<span className="text-primary">AI</span></span>
        </div>

        <nav className="hidden md:flex items-center gap-6">
          {navigationData.map((item, index) => (
            <a
              key={index}
              href={item.href}
              className={`text-sm font-medium transition-colors hover:text-primary ${
                item.isActive ? "text-primary font-bold" : "text-muted-foreground"
              }`}
            >
              {item.title}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <Button size="sm" asChild>
            <a href="/app">Launch App →</a>
          </Button>
        </div>
      </div>
    </header>
  );
}
