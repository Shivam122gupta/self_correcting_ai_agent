import React from "react";
import { Button } from "@/components/ui/button";

export interface AvatarList {
  image: string;
}

export interface HeroSectionProps {
  avatarList: AvatarList[];
}

export default function HeroSection({ avatarList }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden py-20 md:py-32">
      <div className="container mx-auto px-4 text-center">
        {/* Avatars & Social Proof */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="flex -space-x-3">
            {avatarList.map((avatar, index) => (
              <img
                key={index}
                src={avatar.image}
                alt={`User ${index + 1}`}
                className="w-10 h-10 rounded-full border-2 border-background object-cover"
              />
            ))}
          </div>
          <div className="text-sm font-medium text-muted-foreground text-left">
            <div className="flex items-center gap-1 text-amber-500 font-bold">
              ★★★★★ <span className="text-foreground font-semibold">5.0</span>
            </div>
            <span>Trusted by 10,000+ AI developers</span>
          </div>
        </div>

        {/* Hero Title & Description */}
        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-foreground max-w-4xl mx-auto mb-6 leading-tight">
          Autonomous Multi-Agent AI That <span className="text-primary">Self-Corrects</span> Until Perfect
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
          Empower your team with a Writer → Reviewer → Reviser workflow powered by Groq Cloud LPUs and LangGraph to guarantee zero hallucinations.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="lg" className="w-full sm:w-auto text-base px-8 py-6 rounded-xl font-bold shadow-lg" asChild>
            <a href="/app">Launch Agent Workspace →</a>
          </Button>
          <Button size="lg" variant="outline" className="w-full sm:w-auto text-base px-8 py-6 rounded-xl font-semibold" asChild>
            <a href="#architecture">Explore Architecture</a>
          </Button>
        </div>
      </div>
    </section>
  );
}
