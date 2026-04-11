import { useState, useCallback, useEffect, useRef } from "react";

export interface CarouselSlide {
  /** Short label shown in the image placeholder area. */
  placeholder: string;
  /** Bold title below the slide image. */
  title: string;
  /** Subtitle / description below the title. */
  description: string;
}

interface CarouselProps {
  slides: CarouselSlide[];
}

/**
 * Minimal CSS-translate carousel matching the approved mockup design.
 *
 * - Arrow-button navigation (prev / next)
 * - Dot pagination with click-to-jump
 * - Keyboard left/right arrow support when the carousel is in the viewport
 * - Wraps around at both ends
 * - No third-party carousel library
 */
export default function Carousel({ slides }: CarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const viewportRef = useRef<HTMLDivElement>(null);

  const goTo = useCallback(
    (index: number) => {
      setCurrentIndex(((index % slides.length) + slides.length) % slides.length);
    },
    [slides.length],
  );

  const prev = useCallback(() => goTo(currentIndex - 1), [currentIndex, goTo]);
  const next = useCallback(() => goTo(currentIndex + 1), [currentIndex, goTo]);

  // Keyboard navigation when carousel is visible in the viewport.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (!viewportRef.current) return;
      const rect = viewportRef.current.getBoundingClientRect();
      const inView = rect.top < window.innerHeight && rect.bottom > 0;
      if (!inView) return;
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [prev, next]);

  return (
    <div className="mt-16">
      <h3 className="mb-2 text-xl font-semibold text-slate-800">
        See the workflow
      </h3>
      <p className="mb-6 text-sm text-slate-500">
        Six screens that cover the full workflow — from assignment to notification.
      </p>

      {/* Viewport */}
      <div
        ref={viewportRef}
        className="relative mx-auto max-w-2xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
        data-testid="carousel-viewport"
      >
        {/* Track */}
        <div
          className="flex"
          style={{
            transform: `translateX(-${currentIndex * 100}%)`,
            transition: "transform 500ms ease-out",
          }}
          data-testid="carousel-track"
        >
          {slides.map((slide, i) => (
            <div
              key={i}
              className="w-full shrink-0 overflow-hidden"
              data-testid={`carousel-slide-${i}`}
            >
              {/* Image placeholder */}
              <div className="flex h-[28rem] items-center justify-center border-b-2 border-dashed border-slate-300 bg-slate-50">
                <span className="px-4 text-center text-sm font-semibold text-slate-400">
                  {slide.placeholder}
                </span>
              </div>
              {/* Caption */}
              <div className="border-t border-slate-100 px-6 py-4">
                <p className="mb-0.5 text-sm font-medium text-slate-700">
                  {slide.title}
                </p>
                <p className="text-sm text-slate-500">{slide.description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Prev arrow */}
        <button
          type="button"
          aria-label="Previous slide"
          onClick={prev}
          className="absolute left-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white/90 text-slate-700 shadow-md transition-colors hover:bg-white hover:text-violet-600"
          data-testid="carousel-prev"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        {/* Next arrow */}
        <button
          type="button"
          aria-label="Next slide"
          onClick={next}
          className="absolute right-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white/90 text-slate-700 shadow-md transition-colors hover:bg-white hover:text-violet-600"
          data-testid="carousel-next"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Dot pagination */}
      <div className="mt-6 flex items-center justify-center gap-2">
        {slides.map((_, i) => (
          <button
            key={i}
            type="button"
            aria-label={`Go to slide ${i + 1}`}
            onClick={() => goTo(i)}
            className="h-2 w-2 rounded-full transition-colors"
            style={{
              backgroundColor: i === currentIndex ? "#7c3aed" : "#cbd5e1",
            }}
            data-testid={`carousel-dot-${i}`}
          />
        ))}
      </div>
    </div>
  );
}
