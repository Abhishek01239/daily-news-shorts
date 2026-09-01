
# Simplified pipeline (user-directed): fetch news + write blog articles (no video/upload)
if __name__ == '__main__':
    import subprocess, sys
    result = subprocess.run([sys.executable, 'src/write_blog_news.py'], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr: print('ERROR:', result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
    print('PIPELINE COMPLETE (blog-only mode)')
