import type { Metadata } from 'next';
import Link from 'next/link';

import { Footer } from '@/components/footer';
import { SITE_NAME } from '@/lib/site';

export const metadata: Metadata = {
  title: `Política de Privacidade | ${SITE_NAME}`,
  description: 'Como André Assistente Imobiliário usa, armazena e exclui dados da conta.',
  alternates: { canonical: '/privacidade' },
};

export default function PrivacidadePage() {
  return (
    <div className='flex flex-1 flex-col bg-surface text-white'>
      <main className='mx-auto w-full max-w-3xl flex-1 px-5 py-12 sm:py-16'>
        <Link
          href='/'
          className='font-mono text-xs uppercase text-primary-on-surface'
        >
          {SITE_NAME}
        </Link>
        <h1 className='mt-8 font-heading text-4xl'>Política de Privacidade</h1>
        <p className='mt-3 text-sm text-white/60'>
          Última atualização: 29 de setembro de 2026
        </p>

        <div className='mt-10 space-y-8 leading-7 text-white/80'>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Dados utilizados
            </h2>
            <p className='mt-2'>
              André Assistente Imobiliário usa o identificador da sua conta do
              WhatsApp, associado a uma chave interna. Alertas, anúncios
              acompanhados e preferências são associados a essa conta. Não
              solicitamos CPF, senha, cartão ou códigos de autenticação. O
              e-mail pode ser solicitado para ativar benefícios de teste quando
              essa oferta estiver disponível.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Conversas e áudio
            </h2>
            <p className='mt-2'>
              Quando a IA está habilitada, mensagens enviadas ao assistente
              podem ser processadas pela OpenAI para identificar a solicitação e
              seus filtros. Áudios são enviados para transcrição somente quando
              esse recurso está habilitado. A memória curta do assistente
              conserva até seis trocas por padrão, por até quatro horas; padrões
              reconhecíveis de e-mail, CPF e cartão são removidos antes de
              armazenar esse contexto. Não usamos o conteúdo para treinar
              modelos próprios.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Finalidade e terceiros
            </h2>
            <p className='mt-2'>
              Usamos os dados para acompanhar anúncios escolhidos por você,
              apresentar dados agregados de mercado e prevenir abuso. Dados de
              alertas não são exibidos a outros usuários. O serviço monitora
              anúncios públicos do OLX e é independente, não afiliado à OLX.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Retenção e exclusão
            </h2>
            <p className='mt-2'>
              O estado operacional de conversas abandonadas expira
              automaticamente em algumas horas; registros de uso diário
              agregados expiram em até dois dias. Para solicitar a exclusão da
              conta, alertas, acompanhamentos, e-mail e estado do assistente,
              envie <code>excluir dados</code> pelo WhatsApp e confirme a
              solicitação. Mensagens já entregues continuam no histórico
              mantido pelo próprio WhatsApp. Registros que precisem ser
              mantidos por obrigação legal seguem os prazos aplicáveis.
            </p>
          </section>
          <section>
            <h2 className='font-heading text-xl text-white'>
              Seus direitos e contato
            </h2>
            <p className='mt-2'>
              Você pode pedir confirmação, acesso, correção ou exclusão pelo
              canal de atendimento pelo WhatsApp ou use o link de contato no
              rodapé do site. Não envie documentos ou credenciais pelo chat.
              Pedidos que dependam de validação exigem um canal de atendimento
              humano informado pelo operador.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
