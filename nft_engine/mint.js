import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { clusterApiUrl, Connection, Keypair, PublicKey } from '@solana/web3.js';
import { Metaplex, keypairIdentity } from '@metaplex-foundation/js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const KEYPAIR_PATH = path.join(__dirname, '../data/nft_minter_keypair.json');
const GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/manjotGG/SolClub/main/metadata';

function loadKeypairFromFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const secretKey = JSON.parse(raw);

  if (!Array.isArray(secretKey) || secretKey.length === 0) {
    throw new Error('Invalid keypair file format: expected non-empty array');
  }

  return Keypair.fromSecretKey(Uint8Array.from(secretKey));
}

function getRarityUri(rarity) {
  let uri;

  if (rarity === 'common') uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/common.json";
  if (rarity === 'mystery') uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/mystery.json";
  if (rarity === 'epic') uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/epic.json";
  if (rarity === 'legendary') uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/legendary.json";

  if (!uri) {
    throw new Error(`Unsupported rarity: ${rarity}. Supported values are common, mystery, epic, legendary.`);
  }

  console.log('Selected rarity:', rarity);
  console.log('Selected URI:', uri);

  return uri;
}

export async function mintNftToWallet(recipientWalletAddress, rarity = 'common') {
  try {
    console.log('Minting NFT...');
    console.log('Requested rarity:', rarity);

    if (!recipientWalletAddress) {
      throw new Error('recipientWalletAddress argument is required');
    }

    const recipientPublicKey = new PublicKey(recipientWalletAddress);
    const walletKeypair = loadKeypairFromFile(KEYPAIR_PATH);

    console.log('Minter wallet:', walletKeypair.publicKey.toString());
    console.log('Recipient wallet:', recipientPublicKey.toString());

    const uri = getRarityUri(rarity);
    const connection = new Connection(clusterApiUrl('devnet'), 'confirmed');
    const balance = await connection.getBalance(
    walletKeypair.publicKey
);

console.log(
    "Minter balance:",
    balance / 1000000000,
    "SOL"
);
    const metaplex = Metaplex.make(connection).use(keypairIdentity(walletKeypair));

    const { nft } = await metaplex.nfts().create({
      uri,
      name: 'SolClub NFT',
      sellerFeeBasisPoints: 0,
      tokenOwner: recipientPublicKey,
    });

    console.log('Mint address:', nft.address.toString());
    console.log('NFT Minted successfully');

    return nft;
  } catch (error) {
    console.error("===== FULL ERROR =====");
    console.error(error);

    if (error.logs) {
        console.error("===== LOGS =====");
        console.error(error.logs);
    }

    if (error.cause) {
        console.error("===== CAUSE =====");
        console.error(error.cause);
    }

    throw error;
}
}

const recipientArg = process.argv[2];
const rarityArg = process.argv[3] || 'common';

(async () => {
  console.log('FILE STARTED');
  if (!recipientArg) {
    console.log('No recipient public key passed. To test call `node mint.js <recipientPublicKey> [rarity]`.');
    return;
  }

  try {
    await mintNftToWallet(recipientArg, rarityArg);
  } catch (error) {
    console.error('Error in IIFE execution:', error);
    process.exitCode = 1;
  }
})();


