import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-background">
      <main className="flex w-full max-w-3xl flex-col gap-8 px-4 py-16 sm:px-8">
        {/* Hero header */}
        <div className="flex flex-col items-center gap-3 text-center sm:items-start sm:text-left">
          <h1 className="font-heading text-4xl leading-tight tracking-tight text-primary sm:text-5xl">
            Imóvel Radar
          </h1>
          <p className="max-w-lg text-lg leading-relaxed text-muted-foreground">
            Monitore anúncios de imóveis no OLX Maceió e receba notificações
            quando novos imóveis corresponderem aos seus filtros.
          </p>
          <Badge variant="outline" className="mt-2 text-xs font-mono uppercase tracking-wider">
            Bot do Telegram ativo
          </Badge>
        </div>

        {/* Status card */}
        <Card>
          <CardHeader>
            <CardTitle>Status do Bot</CardTitle>
            <CardDescription>
              O bot do Telegram está rodando e monitorando novos anúncios
              diariamente.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                Fonte
              </span>
              <span className="font-sans font-semibold">OLX Maceió</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                Frequência
              </span>
              <span className="font-sans font-semibold">Diária (08:00)</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                Comando
              </span>
              <span className="font-mono text-sm font-semibold">/novo_alerta</span>
            </div>
          </CardContent>
        </Card>

        {/* Next steps card */}
        <Card>
          <CardHeader>
            <CardTitle>Próximos Passos</CardTitle>
            <CardDescription>
              Funcionalidades planejadas para o dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-3 text-sm">
              <li className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-secondary/20 font-mono text-xs font-bold text-secondary">
                  1
                </span>
                <span>
                  <span className="font-semibold">Dashboard de alertas</span>{" "}
                  — visualize e gerencie seus alertas cadastrados
                </span>
              </li>
              <li className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-secondary/20 font-mono text-xs font-bold text-secondary">
                  2
                </span>
                <span>
                  <span className="font-semibold">Histórico de anúncios</span>{" "}
                  — veja os imóveis já notificados
                </span>
              </li>
              <li className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-secondary/20 font-mono text-xs font-bold text-secondary">
                  3
                </span>
                <span>
                  <span className="font-semibold">API pública</span> —{" "}
                  exponha dados do scraper via HTTP
                </span>
              </li>
            </ul>
          </CardContent>
        </Card>

        {/* CTA */}
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <a
            href="https://t.me/seu_bot_aqui"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-transparent bg-primary px-2.5 text-sm font-medium text-primary-foreground whitespace-nowrap transition-all outline-none select-none hover:bg-primary/80 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          >
            Abrir no Telegram
          </a>
          <a
            href="/docs"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border bg-background px-2.5 text-sm font-medium text-foreground whitespace-nowrap transition-all outline-none select-none hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          >
            Ver documentação
          </a>
        </div>
      </main>
    </div>
  );
}