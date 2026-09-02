import { Fragment } from 'react'

/** Models emit lightweight markdown (**bold**) whether or not you ask them not to, and raw
 *  asterisks in a chat bubble look like a bug. Renders bold segments only — deliberately not a
 *  full markdown parser, and never via dangerouslySetInnerHTML, since this is model output. */
export function AgentText({ text }: { text: string }) {
  return (
    <>
      {text.split('\n').map((line, lineIndex) => (
        <Fragment key={lineIndex}>
          {lineIndex > 0 && <br />}
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
            part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
              <strong key={i} className="font-semibold">
                {part.slice(2, -2)}
              </strong>
            ) : (
              <Fragment key={i}>{part}</Fragment>
            ),
          )}
        </Fragment>
      ))}
    </>
  )
}
