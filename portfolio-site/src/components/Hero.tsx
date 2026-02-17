"use client";

import { motion } from "framer-motion";
import { ArrowDown, Download } from "lucide-react";

export default function Hero() {
  const scrollToProjects = () => {
    document.getElementById("projects")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Coordinate System */}
      <div className="absolute top-8 left-8 font-mono text-xs text-cyan opacity-40 hidden md:block">
        <div>[00.00, 00.00]</div>
      </div>
      <div className="absolute bottom-8 right-8 font-mono text-xs text-purple opacity-40 hidden md:block">
        <div>[100.00, 100.00]</div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-12 py-20">
        <div className="space-y-8">
          {/* Name with Glitch Effect */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="font-mono text-cyan text-sm md:text-base mb-4 tracking-wider">
              {"<DEVELOPER />"}
            </div>
            <h1 className="text-6xl md:text-8xl lg:text-9xl font-bold tracking-tighter">
              Matthew
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan via-purple to-pink">
                Russell
              </span>
            </h1>
          </motion.div>

          {/* Subheadline */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="max-w-3xl"
          >
            <h2 className="text-2xl md:text-4xl lg:text-5xl font-medium text-cyan leading-tight">
              Building AI systems that multiply human capability
            </h2>
          </motion.div>

          {/* Description */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="max-w-2xl"
          >
            <p className="text-lg md:text-xl text-gray-400 leading-relaxed">
              Full-stack engineer specializing in AI-powered automation,
              developer tools, and scalable systems. Creator of OpenClaw plugins
              used by engineers worldwide.
            </p>
          </motion.div>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="flex flex-col sm:flex-row gap-4 pt-4"
          >
            <button
              onClick={scrollToProjects}
              className="group relative px-8 py-4 bg-cyan text-space font-semibold rounded-lg overflow-hidden transition-all duration-300 hover:shadow-[0_0_30px_rgba(0,217,255,0.5)] hover:scale-105"
            >
              <span className="relative z-10 flex items-center justify-center gap-2">
                View My Work
                <ArrowDown className="w-5 h-5 group-hover:translate-y-1 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-gradient-to-r from-cyan via-purple to-pink opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </button>

            <a
              href="/resume.pdf"
              download="MatthewRussell_resume.pdf"
              className="group px-8 py-4 glass border border-cyan/30 text-cyan font-semibold rounded-lg transition-all duration-300 hover:border-cyan hover:shadow-[0_0_20px_rgba(0,217,255,0.3)] hover:scale-105 flex items-center justify-center gap-2"
            >
              Download Resume
              <Download className="w-5 h-5 group-hover:translate-y-1 transition-transform" />
            </a>
          </motion.div>

          {/* Tech Stack Indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 1 }}
            className="pt-12"
          >
            <div className="flex flex-wrap gap-3 font-mono text-xs md:text-sm opacity-60">
              <span className="px-3 py-1 border border-cyan/20 rounded-full">
                TypeScript
              </span>
              <span className="px-3 py-1 border border-purple/20 rounded-full">
                React
              </span>
              <span className="px-3 py-1 border border-pink/20 rounded-full">
                Rust
              </span>
              <span className="px-3 py-1 border border-cyan/20 rounded-full">
                AI/ML
              </span>
              <span className="px-3 py-1 border border-purple/20 rounded-full">
                Systems
              </span>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Floating Geometric Shapes */}
      <motion.div
        animate={{
          y: [0, -20, 0],
          rotate: [0, 180, 360],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: "linear",
        }}
        className="absolute top-1/4 right-1/4 w-32 h-32 border border-cyan/10 rounded-lg pointer-events-none hidden lg:block"
      />
      <motion.div
        animate={{
          y: [0, 20, 0],
          rotate: [360, 180, 0],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "linear",
        }}
        className="absolute bottom-1/4 left-1/4 w-24 h-24 border border-purple/10 pointer-events-none hidden lg:block"
        style={{ clipPath: "polygon(50% 0%, 100% 100%, 0% 100%)" }}
      />
    </section>
  );
}
