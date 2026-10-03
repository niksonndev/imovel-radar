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

/// Id do botão tocado — ou o rótulo, quando o cliente só manda o texto.
///
/// Um toque **não tem uma forma única**: resposta interativa (WA Web), botões
/// antigos (`buttonsResponseMessage`), resposta de template e item de lista. A
/// primeira versão só entendia a resposta interativa e o toque caía no vazio:
/// o `text_content()` devolve `None` e a mensagem era descartada em silêncio.
/// Aqui todas as formas são tentadas e, quando só vem o rótulo, ele é devolvido
/// — os rótulos são as próprias opções do roteador ("Novo alerta", "Confirmar").
pub fn button_reply(message: &wa::Message) -> Option<String> {
    use whatsapp_rust::wacore::proto_helpers::MessageExt;

    let base = message.get_base_message();
    if let Some(response) = base.interactive_response_message.as_option() {
        if let Some(id) = native_flow_reply_id(response) {
            return Some(id);
        }
        let from_body = response
            .body
            .as_option()
            .and_then(|body| body.text.as_deref())
            .and_then(non_empty);
        if from_body.is_some() {
            return from_body;
        }
    }
    if let Some(legacy) = base.buttons_response_message.as_option() {
        if let Some(id) = legacy.selected_button_id.as_deref().and_then(non_empty) {
            return Some(id);
        }
        if let Some(wa::message::buttons_response_message::Response::SelectedDisplayText(text)) =
            legacy.response.as_ref()
        {
            let text = non_empty(text);
            if text.is_some() {
                return text;
            }
        }
    }
    if let Some(template) = base.template_button_reply_message.as_option() {
        if let Some(id) = template.selected_id.as_deref().and_then(non_empty) {
            return Some(id);
        }
        let text = template
            .selected_display_text
            .as_deref()
            .and_then(non_empty);
        if text.is_some() {
            return text;
        }
    }
    if let Some(list) = base.list_response_message.as_option() {
        if let Some(id) = list
            .single_select_reply
            .as_option()
            .and_then(|reply| reply.selected_row_id.as_deref())
            .and_then(non_empty)
        {
            return Some(id);
        }
        let title = list.title.as_deref().and_then(non_empty);
        if title.is_some() {
            return title;
        }
    }
    None
}

fn native_flow_reply_id(response: &wa::message::InteractiveResponseMessage) -> Option<String> {
    let payload = response.interactive_response_message.as_ref()?;
    match payload {
        wa::message::interactive_response_message::InteractiveResponseMessage::NativeFlowResponseMessage(
            native,
        ) => native.params_json.as_deref().and_then(params_json_id),
    }
}

/// Nomes dos campos preenchidos da mensagem, sem valores.
///
/// Serve para diagnosticar um toque que não reconhecemos: sem isto, "o botão
/// não funciona" e "a mensagem nem chegou" ficam indistinguíveis no log.
pub fn shape(message: &wa::Message) -> String {
    use whatsapp_rust::wacore::proto_helpers::MessageExt;

    let Ok(value) = serde_json::to_value(message.get_base_message()) else {
        return "ilegivel".to_string();
    };
    let Some(map) = value.as_object() else {
        return "ilegivel".to_string();
    };
    let keys: Vec<&str> = map
        .iter()
        .filter(|(_, value)| !value.is_null())
        .map(|(key, _)| key.as_str())
        .collect();
    if keys.is_empty() {
        return "vazia".to_string();
    }
    keys.join(",")
}

/// `id` do botão dentro do `params_json`; clientes variam o nome da chave.
fn params_json_id(params: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(params).ok()?;
    for key in ["id", "button_id", "selected_id", "selectedId", "row_id"] {
        if let Some(found) = value.get(key).and_then(serde_json::Value::as_str) {
            if let Some(found) = non_empty(found) {
                return Some(found);
            }
        }
    }
    for key in ["display_text", "title", "text"] {
        if let Some(found) = value.get(key).and_then(serde_json::Value::as_str) {
            if let Some(found) = non_empty(found) {
                return Some(found);
            }
        }
    }
    None
}

fn non_empty(value: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
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
    fn le_toque_de_botao_antigo() {
        let message = wa::Message {
            buttons_response_message: MessageField::some(wa::message::ButtonsResponseMessage {
                selected_button_id: Some("2".into()),
                response: Some(
                    wa::message::buttons_response_message::Response::SelectedDisplayText(
                        "Meus alertas".into(),
                    ),
                ),
                ..Default::default()
            }),
            ..Default::default()
        };
        assert_eq!(button_reply(&message).as_deref(), Some("2"));
    }

    #[test]
    fn le_toque_de_template_e_de_lista() {
        let template = wa::Message {
            template_button_reply_message: MessageField::some(
                wa::message::TemplateButtonReplyMessage {
                    selected_id: Some("1".into()),
                    selected_display_text: Some("Confirmar".into()),
                    ..Default::default()
                },
            ),
            ..Default::default()
        };
        assert_eq!(button_reply(&template).as_deref(), Some("1"));

        let lista = wa::Message {
            list_response_message: MessageField::some(wa::message::ListResponseMessage {
                title: Some("Jatiúca".into()),
                single_select_reply: MessageField::some(
                    wa::message::list_response_message::SingleSelectReply {
                        selected_row_id: Some("3".into()),
                    },
                ),
                ..Default::default()
            }),
            ..Default::default()
        };
        assert_eq!(button_reply(&lista).as_deref(), Some("3"));
    }

    #[test]
    fn params_json_sem_id_usa_o_rotulo() {
        let message = wa::Message {
            interactive_response_message: MessageField::some(
                wa::message::InteractiveResponseMessage {
                    interactive_response_message: Some(
                        wa::message::interactive_response_message::InteractiveResponseMessage::NativeFlowResponseMessage(
                            Box::new(
                                wa::message::interactive_response_message::NativeFlowResponseMessage {
                                    name: Some("quick_reply".into()),
                                    params_json: Some(r#"{"display_text":"Ajuda"}"#.into()),
                                    version: Some(1),
                                },
                            ),
                        ),
                    ),
                    ..Default::default()
                },
            ),
            ..Default::default()
        };
        assert_eq!(button_reply(&message).as_deref(), Some("Ajuda"));
    }

    #[test]
    fn shape_nao_vaza_conteudo() {
        let message = wa::Message {
            conversation: Some("segredo do usuario".into()),
            ..Default::default()
        };
        let shape = shape(&message);
        assert!(shape.contains("conversation"));
        assert!(!shape.contains("segredo"));
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
