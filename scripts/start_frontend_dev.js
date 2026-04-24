const { spawn } = require('node:child_process')
const http = require('node:http')

const HOST = 'localhost'
const PORT = 5173

function request(path) {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host: HOST,
        port: PORT,
        path,
        timeout: 800,
      },
      (res) => {
        let body = ''
        res.setEncoding('utf8')
        res.on('data', (chunk) => {
          body += chunk
        })
        res.on('end', () => {
          resolve({ statusCode: res.statusCode, body })
        })
      },
    )

    req.on('timeout', () => {
      req.destroy()
      resolve(null)
    })
    req.on('error', () => {
      resolve(null)
    })
  })
}

async function isExistingKokoroFrontend() {
  const index = await request('/')
  if (!index || index.statusCode !== 200 || !index.body.includes('<title>Kokoro</title>')) {
    return false
  }

  const main = await request('/src/main.ts')
  return Boolean(
    main
      && main.statusCode === 200
      && main.body.includes("import App from './App.vue'")
      && main.body.includes("createPinia"),
  )
}

function startVite() {
  const child = spawn('npm', ['run', 'dev', '--prefix', 'frontend'], {
    stdio: 'inherit',
    shell: true,
  })

  const forwardSignal = (signal) => {
    if (!child.killed) {
      child.kill(signal)
    }
  }

  process.on('SIGINT', () => forwardSignal('SIGINT'))
  process.on('SIGTERM', () => forwardSignal('SIGTERM'))

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal)
      return
    }
    process.exit(code ?? 1)
  })
}

async function main() {
  if (await isExistingKokoroFrontend()) {
    console.log(`Kokoro frontend 已在 http://${HOST}:${PORT} 运行，复用现有 Vite 进程。`)
    process.exit(0)
  }

  startVite()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
