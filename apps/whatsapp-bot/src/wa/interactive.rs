//! Botões de resposta rápida do WhatsApp.
//!
//! O WhatsApp aceita no máximo 3 botões por mensagem, e um toque **não** chega
//! como texto: vem em `interactiveResponseMessage`. Por isso o `id` de cada
//! botão é a própria opção numerada do menu ("1", "2", ...), e o toque entra no
//! roteador exatamente como se a pessoa tivesse digitado o número. O texto
//! numerado continua no corpo da mensagem como fallback — se o cliente não
//! renderizar os botões, o fluxo segue funcionando.

use whatsapp_rust::buffa::MessageField;
use whatsapp_rust::prelude::wa;

use crate::handlers::Button;

/// Limite do WhatsApp para botões de resposta rápida.
pub const MAX_BUTTONS: usize = 3;

fn button_params(button: &Button) -> String {
    serde_json::json!({"display_text": button.label, "id": button.id}).to_string()
}

/// Monta a mensagem interativa com botões `quick_reply`.
pub fn quick_replies(body: &str, buttons: &[Button]) -> wa::Message {
    let buttons = buttons
        .iter()
        .take(MAX_BUTTONS)
        .map(|button| wa::message::interactive_message::native_flow_message::NativeFlowButton {
            name: Some("quick_reply".to_string()),
            button_params_json: Some(button_params(button)),
        })
        .collect();
    wa::Message {
        interactive_message: MessageField::some(wa::message::InteractiveMessage {
            body: MessageField::some(wa::message::interactive_message::Body {
                text: Some(body.to_string()),
            }),
            interactive_message: Some(
                wa::message::interactive_message::InteractiveMessage::NativeFlowMessage(Box::new(
                    wa::message::interactive_message::NativeFlowMessage {
                        buttons,
                        message_params_json: None,
                        message_version: Some(1),
                    },
                )),
            ),
            ..Default::default()
        }),
        ..Default::default()
    }
}

/// `id` do botão tocado, quando a mensagem recebida é uma resposta interativa.
///
/// Devolve `None` para qualquer mensagem que não seja um toque em botão, para o
/// chamador seguir com o texto normal.
pub fn button_reply(message: &wa::Message) -> Option<String> {
    use whatsapp_rust::wacore::proto_helpers::MessageExt;

    let response = message
        .get_base_message()
        .interactive_response_message
        .as_option()?;
    let params = match response.interactive_response_message.as_ref()? {
        wa::message::interactive_response_message::InteractiveResponseMessage::NativeFlowResponseMessage(
            native,
        ) => native.params_json.as_deref()?,
    };
    let value: serde_json::Value = serde_json::from_str(params).ok()?;
    value
        .get("id")
        .and_then(serde_json::Value::as_str)
        .map(str::to_string)
        .filter(|id| !id.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn botoes() -> Vec<Button> {
        vec![
            Button {
                id: "1".into(),
                label: "Novo alerta".into(),
            },
            Button {
                id: "2".into(),
                label: "Meus alertas".into(),
            },
            Button {
                id: "3".into(),
                label: "Ajuda".into(),
            },
            Button {
                id: "4".into(),
                label: "Ignorado".into(),
            },
        ]
    }

    #[test]
    fn monta_no_maximo_tres_botoes_quick_reply() {
        let message = quick_replies("menu", &botoes());
        let interactive = message.interactive_message.as_option().expect("interactive");
        assert_eq!(
            interactive
                .body
                .as_option()
                .and_then(|body| body.text.as_deref()),
            Some("menu")
        );
        let Some(
            wa::message::interactive_message::InteractiveMessage::NativeFlowMessage(native),
        ) = interactive.interactive_message.as_ref()
        else {
            panic!("native flow");
        };
        assert_eq!(native.buttons.len(), MAX_BUTTONS);
        assert_eq!(native.buttons[0].name.as_deref(), Some("quick_reply"));
        let params: serde_json::Value =
            serde_json::from_str(native.buttons[0].button_params_json.as_deref().unwrap()).unwrap();
        assert_eq!(params["id"], "1");
        assert_eq!(params["display_text"], "Novo alerta");
        assert!(native.buttons.iter().all(|b| b.name.as_deref() == Some("quick_reply")));
    }

    #[test]
    fn le_o_id_do_botao_tocado() {
        let message = wa::Message {
            interactive_response_message: MessageField::some(
                wa::message::InteractiveResponseMessage {
                    body: MessageField::none(),
                    context_info: MessageField::none(),
                    interactive_response_message: Some(
                        wa::message::interactive_response_message::InteractiveResponseMessage::NativeFlowResponseMessage(
                            Box::new(
                                wa::message::interactive_response_message::NativeFlowResponseMessage {
                                    name: Some("quick_reply".into()),
                                    params_json: Some(r#"{"id":"2","display_text":"Meus alertas"}"#.into()),
                                    version: Some(1),
                                },
                            ),
                        ),
                    ),
                },
            ),
            ..Default::default()
        };
        assert_eq!(button_reply(&message).as_deref(), Some("2"));
    }

    #[test]
    fn texto_comum_nao_e_toque_em_botao() {
        let message = wa::Message {
            conversation: Some("2".into()),
            ..Default::default()
        };
        assert_eq!(button_reply(&message), None);
    }

    #[test]
    fn params_json_invalido_nao_quebra() {
        let message = wa::Message {
            interactive_response_message: MessageField::some(
                wa::message::InteractiveResponseMessage {
                    body: MessageField::none(),
                    context_info: MessageField::none(),
                    interactive_response_message: Some(
                        wa::message::interactive_response_message::InteractiveResponseMessage::NativeFlowResponseMessage(
                            Box::new(
                                wa::message::interactive_response_message::NativeFlowResponseMessage {
                                    name: None,
                                    params_json: Some("nao e json".into()),
                                    version: None,
                                },
                            ),
                        ),
                    ),
                },
            ),
            ..Default::default()
        };
        assert_eq!(button_reply(&message), None);
    }

    #[test]
    fn envio_aceita_vetor_vazio() {
        // Sem botões a mensagem interativa não faz sentido; o chamador nunca
        // deve cair aqui, mas o construtor não pode entrar em pânico.
        let message = quick_replies("menu", &[]);
        let interactive = message.interactive_message.as_option().expect("interactive");
        let Some(
            wa::message::interactive_message::InteractiveMessage::NativeFlowMessage(native),
        ) = interactive.interactive_message.as_ref()
        else {
            panic!("native flow");
        };
        assert!(native.buttons.is_empty());
    }
}
