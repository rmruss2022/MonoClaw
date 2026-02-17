"use client";

import { motion } from "framer-motion";
import { Mail, Phone, MapPin, Github, Linkedin, Send } from "lucide-react";
import { useState } from "react";

const contactInfo = [
  {
    icon: Mail,
    label: "Email",
    value: "mattrussellc@gmail.com",
    href: "mailto:mattrussellc@gmail.com",
  },
  {
    icon: Phone,
    label: "Phone",
    value: "+1 (201) 783-7383",
    href: "tel:+12017837383",
  },
  {
    icon: MapPin,
    label: "Location",
    value: "New York, NY",
    href: null,
  },
];

const socialLinks = [
  {
    icon: Github,
    label: "GitHub",
    href: "https://github.com/rmruss2022",
    color: "cyan",
  },
  {
    icon: Linkedin,
    label: "LinkedIn",
    href: "https://linkedin.com/in/matthewrussellc",
    color: "purple",
  },
];

export default function Contact() {
  const [formState, setFormState] = useState({
    name: "",
    email: "",
    message: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<"idle" | "success" | "error">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    // Simulate form submission (replace with actual API call later)
    await new Promise((resolve) => setTimeout(resolve, 1500));

    setIsSubmitting(false);
    setSubmitStatus("success");
    setFormState({ name: "", email: "", message: "" });

    setTimeout(() => setSubmitStatus("idle"), 5000);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormState((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  return (
    <section id="contact" className="relative py-20 md:py-32">
      {/* Background Accent */}
      <div className="absolute inset-0 bg-gradient-to-t from-space-light/50 to-transparent pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-6 md:px-12">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16 text-center"
        >
          <div className="font-mono text-sm mb-4" style={{ color: "var(--accent-cyan)" }}>
            {"<GET_IN_TOUCH />"}
          </div>
          <h2 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6">
            Let's Build Something
          </h2>
          <p className="text-lg md:text-xl max-w-2xl mx-auto leading-relaxed" style={{ color: "var(--gray-400)" }}>
            I'm always interested in challenging projects, developer tools, and
            AI automation opportunities. Whether you're hiring, collaborating on
            a side project, or just want to talk about AI agents and automation
            - I'd love to hear from you.
          </p>
          <div
            className="h-1.5 w-40 mt-6 rounded-full mx-auto"
            style={{
              background: "linear-gradient(to right, var(--accent-cyan), var(--accent-pink), var(--accent-purple))",
              boxShadow: "0 0 10px rgba(0, 217, 255, 0.5)",
            }}
          />
        </motion.div>

        {/* Contact Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          {/* Left Column: Contact Info */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="space-y-8"
          >
            {/* Contact Methods */}
            <div className="space-y-4">
              {contactInfo.map((info) => {
                const Icon = info.icon;
                const Wrapper = info.href ? "a" : "div";
                return (
                  <Wrapper
                    key={info.label}
                    {...(info.href
                      ? { href: info.href, target: "_blank", rel: "noopener noreferrer" }
                      : {})}
                    className="glass rounded-xl p-6 border border-transparent hover:border-cyan/30 transition-all duration-300 flex items-center gap-4 group cursor-pointer"
                  >
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-cyan/20 to-purple/20 border border-cyan/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Icon className="w-6 h-6 text-cyan" />
                    </div>
                    <div>
                      <div className="text-sm text-gray-400 font-mono">
                        {info.label}
                      </div>
                      <div className="text-lg font-semibold group-hover:text-cyan transition-colors">
                        {info.value}
                      </div>
                    </div>
                  </Wrapper>
                );
              })}
            </div>

            {/* Social Links */}
            <div className="glass rounded-xl p-6 border border-purple/20">
              <h3 className="text-xl font-bold mb-4">Connect</h3>
              <div className="flex gap-4">
                {socialLinks.map((social) => {
                  const Icon = social.icon;
                  return (
                    <a
                      key={social.label}
                      href={social.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-12 h-12 rounded-lg border flex items-center justify-center hover:scale-110 transition-all"
                      style={{
                        background: `linear-gradient(135deg, rgba(var(${social.color === "cyan" ? "0, 217, 255" : "176, 38, 255"}), 0.2), rgba(var(${social.color === "cyan" ? "0, 217, 255" : "176, 38, 255"}), 0.1))`,
                        borderColor: `rgba(var(${social.color === "cyan" ? "0, 217, 255" : "176, 38, 255"}), 0.3)`,
                      }}
                      aria-label={social.label}
                    >
                      <Icon
                        className="w-5 h-5"
                        style={{ color: `var(--accent-${social.color})` }}
                      />
                    </a>
                  );
                })}
              </div>
            </div>

            {/* Resume Download */}
            <a
              href="/resume.pdf"
              download="MatthewRussell_resume.pdf"
              className="glass rounded-xl p-6 border border-pink/30 hover:border-pink hover:shadow-[0_0_30px_rgba(255,0,128,0.2)] transition-all duration-300 flex items-center justify-between group"
            >
              <div>
                <div className="text-sm text-gray-400 font-mono mb-1">
                  Download
                </div>
                <div className="text-xl font-bold group-hover:text-pink transition-colors">
                  Resume PDF
                </div>
              </div>
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-pink/20 to-purple/20 border border-pink/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                <svg
                  className="w-6 h-6 text-pink"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
            </a>
          </motion.div>

          {/* Right Column: Contact Form */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <form
              onSubmit={handleSubmit}
              className="glass rounded-xl p-8 border border-cyan/20 space-y-6"
            >
              <h3 className="text-2xl font-bold mb-6">Send a Message</h3>

              {/* Name Input */}
              <div>
                <label
                  htmlFor="name"
                  className="block text-sm font-medium text-gray-400 mb-2"
                >
                  Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formState.name}
                  onChange={handleChange}
                  required
                  className="w-full px-4 py-3 bg-space-light border border-cyan/20 rounded-lg focus:border-cyan focus:outline-none focus:ring-2 focus:ring-cyan/20 transition-all text-white"
                  placeholder="Your name"
                />
              </div>

              {/* Email Input */}
              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-gray-400 mb-2"
                >
                  Email
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formState.email}
                  onChange={handleChange}
                  required
                  className="w-full px-4 py-3 bg-space-light border border-cyan/20 rounded-lg focus:border-cyan focus:outline-none focus:ring-2 focus:ring-cyan/20 transition-all text-white"
                  placeholder="your.email@example.com"
                />
              </div>

              {/* Message Input */}
              <div>
                <label
                  htmlFor="message"
                  className="block text-sm font-medium text-gray-400 mb-2"
                >
                  Message
                </label>
                <textarea
                  id="message"
                  name="message"
                  value={formState.message}
                  onChange={handleChange}
                  required
                  rows={6}
                  className="w-full px-4 py-3 bg-space-light border border-cyan/20 rounded-lg focus:border-cyan focus:outline-none focus:ring-2 focus:ring-cyan/20 transition-all text-white resize-none"
                  placeholder="Tell me about your project..."
                />
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full px-6 py-4 bg-gradient-to-r from-cyan to-purple text-white font-semibold rounded-lg hover:shadow-[0_0_30px_rgba(0,217,255,0.5)] transition-all duration-300 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                {isSubmitting ? (
                  <span>Sending...</span>
                ) : (
                  <>
                    <span>Get In Touch</span>
                    <Send className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>

              {/* Success Message */}
              {submitStatus === "success" && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-cyan/10 border border-cyan/30 rounded-lg text-cyan text-sm text-center"
                >
                  ✓ Message sent successfully! I'll get back to you soon.
                </motion.div>
              )}
            </form>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
