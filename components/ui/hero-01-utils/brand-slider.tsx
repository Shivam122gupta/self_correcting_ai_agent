import React from "react";

export interface BrandList {
  image: string;
  lightimg?: string;
  name: string;
}

export interface BrandSliderProps {
  brandList: BrandList[];
}

export default function BrandSlider({ brandList }: BrandSliderProps) {
  return (
    <div className="py-12 border-y bg-muted/30 overflow-hidden">
      <div className="container mx-auto px-4 text-center mb-6">
        <p className="text-xs uppercase font-bold tracking-widest text-muted-foreground">
          Powering Autonomous Intelligence For Leading Enterprises
        </p>
      </div>
      <div className="flex items-center justify-center gap-12 flex-wrap max-w-5xl mx-auto px-4 opacity-75">
        {brandList.map((brand, index) => (
          <img
            key={index}
            src={brand.image}
            alt={brand.name}
            className="h-8 object-contain dark:invert transition-opacity hover:opacity-100"
          />
        ))}
      </div>
    </div>
  );
}
