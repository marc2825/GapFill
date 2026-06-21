import { readFile } from 'node:fs/promises';

const PNG_SIGNATURE = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);

function parseInternationalText(data) {
  const keywordEnd = data.indexOf(0);
  if (keywordEnd === -1) return null;

  const keyword = data.subarray(0, keywordEnd).toString('latin1');
  let offset = keywordEnd + 1;
  const compressionFlag = data[offset];
  offset += 2;
  offset = data.indexOf(0, offset) + 1;
  offset = data.indexOf(0, offset) + 1;

  if (compressionFlag !== 0 || offset <= 1) return null;
  return [keyword, data.subarray(offset).toString('utf8')];
}

export async function getPngTextMetadata(filePath) {
  const image = await readFile(filePath);
  if (!image.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)) {
    throw new Error(`Invalid PNG signature: ${filePath}`);
  }

  const metadata = new Map();
  let offset = PNG_SIGNATURE.length;

  while (offset + 12 <= image.length) {
    const dataLength = image.readUInt32BE(offset);
    const type = image.subarray(offset + 4, offset + 8).toString('ascii');
    const dataEnd = offset + 8 + dataLength;
    if (dataEnd + 4 > image.length) throw new Error(`Invalid PNG chunk: ${filePath}`);
    const data = image.subarray(offset + 8, dataEnd);

    if (type === 'tEXt') {
      const separator = data.indexOf(0);
      if (separator !== -1) {
        metadata.set(
          data.subarray(0, separator).toString('latin1'),
          data.subarray(separator + 1).toString('latin1'),
        );
      }
    } else if (type === 'iTXt') {
      const entry = parseInternationalText(data);
      if (entry) metadata.set(...entry);
    }

    offset = dataEnd + 4;
    if (type === 'IEND') break;
  }

  return metadata;
}

export async function getEmbeddedText(filePath) {
  return (await readFile(filePath)).toString('utf8');
}
