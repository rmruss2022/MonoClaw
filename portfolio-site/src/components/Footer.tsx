"use client";

import { Github, Linkedin, Mail } from "lucide-react";

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="relative py-12 border-t border-cyan/10">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          {/* Left: Copyright */}
          <div className="text-center md:text-left">
            <p className="text-gray-400 text-sm font-mono">
              © {currentYear} Matthew Russell
            </p>
            <p className="text-gray-500 text-xs mt-1">
              Built with Next.js, TypeScript, and Tailwind CSS
            </p>
          </div>

          {/* Center: Quick Links */}
          <div className="flex gap-6 text-sm">
            <a
              href="#projects"
              className="text-gray-400 hover:text-cyan transition-colors"
            >
              Projects
            </a>
            <a
              href="#experience"
              className="text-gray-400 hover:text-cyan transition-colors"
            >
              Experience
            </a>
            <a
              href="#skills"
              className="text-gray-400 hover:text-cyan transition-colors"
            >
              Skills
            </a>
            <a
              href="#contact"
              className="text-gray-400 hover:text-cyan transition-colors"
            >
              Contact
            </a>
          </div>

          {/* Right: Social Links */}
          <div className="flex gap-4">
            <a
              href="https://github.com/rmruss2022"
              target="_blank"
              rel="noopener noreferrer"
              className="w-10 h-10 rounded-lg bg-space-light border border-cyan/20 flex items-center justify-center hover:border-cyan hover:shadow-[0_0_15px_rgba(0,217,255,0.3)] transition-all"
              aria-label="GitHub"
            >
              <Github className="w-5 h-5 text-cyan" />
            </a>
            <a
              href="https://linkedin.com/in/matthewrussellc"
              target="_blank"
              rel="noopener noreferrer"
              className="w-10 h-10 rounded-lg bg-space-light border border-purple/20 flex items-center justify-center hover:border-purple hover:shadow-[0_0_15px_rgba(176,38,255,0.3)] transition-all"
              aria-label="LinkedIn"
            >
              <Linkedin className="w-5 h-5 text-purple" />
            </a>
            <a
              href="mailto:mattrussellc@gmail.com"
              className="w-10 h-10 rounded-lg bg-space-light border border-pink/20 flex items-center justify-center hover:border-pink hover:shadow-[0_0_15px_rgba(255,0,128,0.3)] transition-all"
              aria-label="Email"
            >
              <Mail className="w-5 h-5 text-pink" />
            </a>
          </div>
        </div>

        {/* Bottom: Made with love message */}
        <div className="mt-8 text-center">
          <p className="text-gray-500 text-xs font-mono">
            Made with{" "}
            <span className="text-pink inline-block animate-pulse">♥</span> and{" "}
            <span className="text-cyan">caffeine</span>
          </p>
        </div>
      </div>
    </footer>
  );
}
