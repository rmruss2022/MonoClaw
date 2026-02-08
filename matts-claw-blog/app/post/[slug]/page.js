import { notFound } from 'next/navigation';
import Link from 'next/link';
import fs from 'fs';
import path from 'path';

// Required for static export - tells Next.js which pages to pre-render
export async function generateStaticParams() {
  const postsDir = path.join(process.cwd(), 'public/posts');
  
  if (!fs.existsSync(postsDir)) {
    return [];
  }
  
  const files = fs.readdirSync(postsDir)
    .filter(f => f.endsWith('.json') && f !== 'index.json');
  
  return files.map(file => ({
    slug: file.replace('.json', '')
  }));
}

// Get post data server-side
async function getPost(slug) {
  const postPath = path.join(process.cwd(), 'public/posts', `${slug}.json`);
  
  if (!fs.existsSync(postPath)) {
    return null;
  }
  
  const postData = fs.readFileSync(postPath, 'utf-8');
  return JSON.parse(postData);
}

export default async function PostPage({ params }) {
  const post = await getPost(params.slug);

  if (!post) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-700 bg-black/50 backdrop-blur-sm">
        <div className="container mx-auto px-6 py-6">
          <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="text-4xl">🦞</div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                Matt's Claw
              </h1>
            </div>
          </Link>
        </div>
      </header>

      {/* Post Content */}
      <article className="container mx-auto px-6 py-12">
        <div className="max-w-4xl mx-auto">
          {/* Post Header */}
          <div className="mb-8">
            <Link
              href="/"
              className="text-cyan-400 hover:underline mb-6 inline-block"
            >
              ← Back to all posts
            </Link>
            <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              {post.title}
            </h1>
            <p className="text-gray-400 mb-4">
              {new Date(post.date).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
            <div className="flex flex-wrap gap-2 mb-6">
              {post.tags?.map((tag) => (
                <span
                  key={tag}
                  className="px-3 py-1 bg-cyan-500/10 text-cyan-400 rounded-full text-xs font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
            <p className="text-xl text-gray-300">{post.summary}</p>
          </div>

          {/* Hero Image */}
          {post.imageUrl && (
            <div className="mb-8 rounded-lg overflow-hidden border border-gray-700">
              <img
                src={post.imageUrl}
                alt={post.title}
                className="w-full"
              />
            </div>
          )}

          {/* Main Content */}
          <div className="prose prose-invert prose-cyan max-w-none">
            <div dangerouslySetInnerHTML={{ __html: formatMarkdown(post.content) }} />
          </div>

          {/* ASCII Diagram */}
          {post.asciiDiagram && (
            <div className="mt-8 bg-gray-900 border border-gray-700 rounded-lg p-6">
              <h3 className="text-xl font-bold mb-4 text-cyan-400">System Architecture</h3>
              <pre className="text-green-400 text-sm leading-tight whitespace-pre overflow-x-auto">
                {post.asciiDiagram}
              </pre>
            </div>
          )}

          {/* Stats */}
          {post.stats && (
            <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(post.stats).map(([key, value]) => (
                <div
                  key={key}
                  className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 text-center"
                >
                  <div className="text-3xl font-bold text-cyan-400 mb-1">
                    {value}
                  </div>
                  <div className="text-sm text-gray-400 capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </article>
    </div>
  );
}

// Simple markdown-to-HTML converter
function formatMarkdown(text) {
  if (!text) return '';
  
  return text
    // Images (before paragraphs)
    .replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" class="w-full rounded-lg border border-gray-700 my-6" />')
    // Headers
    .replace(/### (.*?)$/gm, '<h3 class="text-2xl font-bold mt-8 mb-4 text-cyan-400">$1</h3>')
    .replace(/## (.*?)$/gm, '<h2 class="text-3xl font-bold mt-10 mb-4 text-cyan-400">$1</h2>')
    .replace(/# (.*?)$/gm, '<h1 class="text-4xl font-bold mt-12 mb-6 text-cyan-400">$1</h1>')
    // Inline formatting
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-bold">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-2 py-1 rounded text-cyan-400">$1</code>')
    // Lists
    .replace(/^- (.*?)$/gm, '<li class="ml-6 mb-2">$1</li>')
    // Paragraphs
    .replace(/\n\n/g, '</p><p class="mb-4">')
    .replace(/^(?!<[hlu]|<\/|<img)/gm, '<p class="mb-4">')
    .replace(/$/gm, '</p>');
}
